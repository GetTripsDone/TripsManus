import os
import sys
import json
from openai import OpenAI
from typing import Dict, Optional, List
import requests
import time
import numpy as np
from sklearn.cluster import KMeans
from local_prompt import Daily_Plan_SysPrompt, Daily_Plan_UserPrompt, PROMPT_JSON, mock_input_text, PROMPT_COMBINE, recomend_scence_str_mock, arrange_route_str_mock
from function_definitions import functions
from prompt import system_prompt, first_user_prompt
from context_data import ContextData, DayPlan, POI, Route
from app.schema import Memory, Message
from think_manager import think_func
from tools_run import arrange, adjust, search_for_poi, search_for_navi, final_answer
from app.logger import logger

'''
    大模型function call做自主规划
'''

#r1 = "deepseek-ai/DeepSeek-R1"
#v3 = "deepseek-ai/DeepSeek-V3"

r1 = "deepseek-r1-250120"
#v3 = "deepseek-v3-241226"
v3 = "deepseek-v3-250324"

async def call_llm(sys_prompt: str, query: str, request_model: str):  # 移除返回类型标注
    client = OpenAI(api_key="cb9729a7-aa90-459f-8315-4ae41a6132f3",
                    base_url="https://ark.cn-beijing.volces.com/api/v3")

    if sys_prompt == "":
        response = client.chat.completions.create(
                model=request_model,
                messages=[
                    {"role": "user", "content": query},
                ],
                stream=True,
                temperature=1.0,
        )
    else:
        response = client.chat.completions.create(
                model=request_model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": query},
                ],
                stream=True,
                temperature=1.0,
        )

    current_section = []
    try:
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                content_piece = chunk.choices[0].delta.content
                #print(content_piece, end="", flush=True)

                # 检查是否包含分割线
                if "---" in content_piece:
                    # 如果当前段落不为空，yield当前段落
                    if current_section:
                        section = "".join(current_section).strip()
                        if section and "---" in section:
                            yield section
                        current_section = []

                current_section.append(content_piece)

        # yield最后一个段落
        if current_section:
            section = "".join(current_section).strip()
            if section and "---" in section:
                yield section

    except Exception as e:
        print(f"Error during streaming: {e}")
        return

def parse_poi_section(section):
    # 使用正则表达式匹配[PX_START]和[PX_END]之间的内容
    import re
    pattern = r'\[(P(\d+)_START)\]\s*([^\[]+?)\s*\[(P\d+_END)\]'
    matches = re.findall(pattern, section)

    if not matches:
        return ('', '')

    # 提取匹配到的景点名称和序号
    # 只返回第一个匹配到的景点信息，因为每个section应该只包含一个景点
    for match in matches:
        start_tag, number, poi_name, end_tag = match
        # 验证标签匹配
        if start_tag.replace('START', '') == end_tag.replace('END', ''):
            return (poi_name.strip(), f'P{number}')
    return ('', '')


def calculate_travel_time_matrix(pois: List[Dict]) -> np.ndarray:
    '''计算POI之间的行驶时间矩阵'''
    n = len(pois)
    matrix = np.zeros((n, n))
    for i in range(n):
        loc1 = np.array(list(map(float, pois[i]['location'].split(','))))
        for j in range(n):
            if i != j:
                loc2 = np.array(list(map(float, pois[j]['location'].split(','))))
                distance = np.linalg.norm(loc1 - loc2)
                matrix[i][j] = distance * 100000 / 60  # 粗略估算行驶时间
    return matrix

def cluster_pois(poi_infos: List[Dict], n_clusters: int = 3) -> Dict[int, List[Dict]]:
    '''将POI聚类并返回按天分组的POI信息，每天对应一个POI簇'''
    valid_pois = []
    locations = []

    for poi in poi_infos:
        if poi and 'location' in poi:
            valid_pois.append(poi)
            lon, lat = map(float, poi['location'].split(','))
            locations.append([lon, lat])

    if not locations:
        return {}

    X = np.array(locations)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    cluster_labels = kmeans.fit_predict(X)

    # 按天分组POI
    daily_pois = {}
    for day in range(n_clusters):
        day_pois = [valid_pois[i] for i in range(len(valid_pois))
                    if cluster_labels[i] == day]

        if not day_pois:
            continue

        # 对POI进行排序（根据评分和时长）
        day_pois.sort(key=lambda x: float(x.get('rating', 0)) / float(x.get('duration', 1)), reverse=True)
        daily_pois[day + 1] = day_pois

    return daily_pois

async def get_recommend(city: str, day: int):
    global v3
    prompt = f"""
    请你根据游玩天数{day}，合理推荐{city}值得一去的景点

    输入格式：markdown
    景点名称按照顺序进行标号：[PX_START] 景点名称 [PX_END]，X是景点编号
    每个景点的完整信息：使用 markdown的分割线进行分割，注意第一行的前置也需要先包含一个分割线

    # 类别1
    ---
    1. [P1_START] 景点名称 [P1_END]
    - 所在地点
    - 景点介绍
    - 预估游玩时长
    ---
    ...
    """

    sections = []
    poi_info_list = []
    poi_counter = 1
    async for section in call_llm("", prompt, v3):
        poi_name, _ = parse_poi_section(section)
        if not poi_name:
            continue
        sections.append(section)
        logger.info(f"收到新的景点信息:\n{section}\n")

        # 从section中提取预估游玩时长
        import re
        duration_match = re.search(r'预估游玩时长[：:]*\s*(\d+(?:\.\d+)?)[^\d]*', section)
        duration = float(duration_match.group(1)) if duration_match else 2.0

        # 请求对应的poi，返回结果
        poi_info = parse_res(execute(poi_name), duration)  # 传入游玩时长
        if not poi_info:
            continue

        poi_info['poi_index'] = f'P{poi_counter}'
        poi_counter += 1
        poi_info_list.append(poi_info)
        logger.info(f"收到新的POI检索信息:\n{poi_info}\n")

    # 对POI进行聚类
    days = int(day)  # 可以根据实际需求调整聚类天数
    clustered_pois = cluster_pois(poi_info_list, days)

    # 创建index2poi字典
    index2poi = {}
    for poi in poi_info_list:
        if 'poi_index' in poi:
            poi_copy = poi.copy()
            del poi_copy['poi_index']
            index2poi[poi['poi_index']] = poi_copy

    return "\n".join(sections), clustered_pois, index2poi


def get_arrange_route(poi_info_list, daily_plan_str):
    '''
    把markdown格式的每日计划和poi_info_list进行整合，一天的这是
    Args:
        poi_info_list: 包含POI信息的字典列表
        daily_plan_str: markdown格式的每日计划字符串
    Returns:
        list: 按时间顺序排列的POI信息列表
    '''
    # 创建POI索引字典，方便查找

    # 提取所有标记对之间的内容
    arranged_pois = []

    import re
    current_poi = None

    for match in re.finditer(r'\[(RESTAURANT|HOTEL|P\d+)_START\]\s*(\d{2}:\d{2}(?:\s*-\s*\d{2}:\d{2})?):?\s*(.+?)\s*\[\1_END\]', daily_plan_str):
        marker_type = match.group(1)
        time_info = match.group(2)
        poi_name = match.group(3)
        # print('marker_type:\n', marker_type)

        # 如果是START标记，处理POI信息
        if marker_type.startswith('P'):
            # 对于Px类型的POI，从poi_info_list中查找
            poi_index = marker_type
            found = False
            for poi_info in poi_info_list:
                if poi_info['poi_index'] == poi_index:
                    current_poi = poi_info.copy()
                    current_poi['time_info'] = time_info
                    found = True
                    break

            if not found:
                # 如果在poi_info_list中没找到，需要重新搜索
                poi_info = parse_res(execute(poi_name)) if poi_name else ('', '', '', '')
                current_poi = {
                    'poi_index': poi_index,
                    'poi_name': poi_name,
                    'location': poi_info[1],
                    'id': poi_info[2],
                    'city_code': poi_info[3],
                    'time_info': time_info
                }
        else:
            # 对于Restaurant和Hotel类型，直接搜索
            poi_info = parse_res(execute(poi_name)) if poi_name else ('', '', '', '')
            current_poi = {
                'poi_index': marker_type,
                'poi_name': poi_name,
                'location': poi_info[1],
                'id': poi_info[2],
                'city_code': poi_info[3],
                'time_info': time_info
            }

        # 如果是END标记且有当前POI，添加到列表中
        arranged_pois.append(current_poi)
        current_poi = None

    # 过滤掉location、id和city_code都为空的POI
    arranged_pois = [poi for poi in arranged_pois if not (poi['location'] == '' or poi['city_code'] == '')]
    return arranged_pois


async def get_travel_plan(city: str, recommend_scene_str: str, start_time:str, end_time:str, poi_info_list:list) -> str:
    global r1, v3
    prompt = f"""# ** 任务说明 **
    1. 请你根据用户所在{city}以及输入的候选景点信息，合理选择一些景点，按照要求，规划一个从{start_time}到{end_time}时间的行程
    2. 行程要包含餐饮和住宿，餐饮和住宿不用给出具体点，给出在什么位置进行餐饮和住宿即可
    3. 包含详细的时间安排和餐饮酒店住宿。你需要考虑一下各个地点之间的路线、距离和时间

    # ** 注意 **
    1.  输出采用markdown格式，每一天的行程安排都用分割线进行分割，第一天的输出前面也要加分割线
    2.  游玩的景区，需要加入 前后缀 [PX_START] 景点名称 [PX_END]，X是景点编号
    3.  早/中/晚吃饭的地方，需要加入 前后缀 [RESTAURANT_START] 餐馆名称描述 [RESTAURANT_END]
    4.  晚上住宿的地方，需要加入 前后缀 [HOTEL_START] 酒店名称描述 [HOTEL_END]
    5.  景点、餐馆、酒店以及对应的时间等所有信息，请统一输出在 前后缀 内部
    6.  你每天的行程安排不要出现重复的景点
    7.  在安排餐饮、酒店住宿的时候要餐馆和酒店的描述必须为"A附近的B"的格式，其中A为景点名称，B为餐馆类型或餐馆特色，例如"故宫附近的早餐店"、"天安门附近的烤鸭店"等
    8.  在安排餐饮、住宿的时候，需要考虑吃饭和回酒店的时间是否合理
    9.  在规划餐厅的时候，要考虑到地方特色，可以结合当地文化安排一些多样性的美食
    10. 在安排景点、餐厅、酒店时候，你要留出一些在路程上耗费的时间，从前一个点到下一个点之间是需要时间buffer的

    # ** 每天示程安排示例如下 **
    ---
    ### 2025-03-24 星期一

    **上午：**
    - [RESTAURANT_START] 08:00 - 09:00: 故宫附近的炒肝儿店 [RESTAURANT_END]
    - [P1_START] 09:00 - 13:00: 故宫博物院 [P1_END]

    **中午：**
    - [RESTAURANT_START] 13:00 - 14:00: 天安门广场附近的烤鸭店 [RESTAURANT_END]

    **下午：**
    - [P2_START] 14:00 - 16:00: 天安门广场 [P2_END]
    - [P5_START] 16:30 - 18:00: 天坛公园 [P5_END]

    **晚上：**
    - [RESTAURANT_START] 18:00 - 19:00: 天坛公园附近的老北京涮肉 [RESTAURANT_END]
    - [HOTEL_START] 19:00: 东城区附近的酒店 [HOTEL_END]

    候选景点信息如下:
    """ + recommend_scene_str + "接下来请你根据上述信息，合理安排行程\n"

    sections = []
    async for section in call_llm("", prompt, v3):
        if not section:
            continue
        print(f"收到新的当日规划:\n{section}\n")

        if "RESTAURANT" not in section and "HOTEL" not in section:
            continue
        sections.append(section)
        section = json.dumps(get_arrange_route(poi_info_list, section), ensure_ascii=False)
        # 这里你可以对每个section立即进行处理
        if not section:
            continue
        print(f"收到新的行程路线信息:\n{section}\n")

    return "\n".join(sections)

def get_daily_plan(travel_plan_str: str) -> str:
    global v3
    prompt = Daily_Plan_UserPrompt + travel_plan_str

    daily_plan_str = call_llm(Daily_Plan_SysPrompt, prompt, v3)

    ret = daily_plan_str
    if "```json" in daily_plan_str and "```" in daily_plan_str:
        json_str = daily_plan_str.split("```json")[1].split("```")[0]
        ret = json_str

    print(f"In Daily Plan:\n{ret}")
    return ret

def execute(
        keywords: str,
    ) -> Dict[str, str]:
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "keywords": keywords,
        "key": '777e65792758b03da95607d112079834',
        "show_fields": "business,opentime_today,rating"
    }

    try:
        response = requests.get(url, params=params)
        time.sleep(1)
        result = response.json()
        if result.get("status") == "1":
            return result
        else:
            return {"error": f"搜索失败: {result.get('info')}"}
    except Exception as e:
        return {"error": f"请求失败: {str(e)}"}


def execute_navi(
    origin: str,
    destination: str,
    city1: str,
    city2: str,
):
    url = "https://restapi.amap.com/v5/direction/transit/integrated"
    mykey = '8ef18770408aef7848eac18e09ec0a17'
    params = {
        "origin": origin,
        "destination": destination,
        "city1": city1,
        "city2": city2,
        "key": mykey,
        "show_fields": 'cost'
    }

    result = []
    try:
        response = requests.get(url, params=params)
        time.sleep(1)
        result = response.json()
        if result.get("status") == "1":
            duration = result['route']['transits'][0]['cost']['duration']
            distance = result['route']['transits'][0]['distance']
            return [duration, distance]
        else:
            return []
    except Exception as e:
        return []


def parse_res(res, duration=None):
    result = res['pois']
    if not result:
        return {}
    result = result[0]
    opentime = result['business'].get('opentime_today', '9:00-18:00')
    # 验证时间格式是否符合x:xx-x:xx格式
    import re
    if not re.match(r'^\d{1,2}:\d{2}-\d{1,2}:\d{2}$', opentime):
        opentime = '9:00-18:00'
    open_time_seconds, close_time_seconds = parse_time_str(opentime)
    return {
        'name': result['name'],
        'location': result['location'],
        'id': result['id'],
        'city_code': result['citycode'],
        'opentime': opentime,
        'open_time_seconds': open_time_seconds,
        'close_time_seconds': close_time_seconds,
        'rating': result['business'].get('rating', '4.5'),
        'duration': float(duration) if duration else 1.0  # 使用传入的游玩时长，默认1小时
    }

def parse_time_str(time_str: str) -> tuple:
    '''将时间字符串转换为秒数'''
    try:
        start_time, end_time = time_str.split('-')
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        return (start_hour * 3600 + start_minute * 60,
                end_hour * 3600 + end_minute * 60)
    except:
        return (9 * 3600, 18 * 3600)  # 默认9:00-18:00

def extract_search_poi(recommend_scene_str):
    response = call_llm(PROMPT_JSON, recommend_scene_str, v3)
    response = json.loads(response)
    # {"name":"八达岭长城", "city": "北京", "description": "保存最完好的明长城精华段", "duration": "5"}
    res_list = []
    for poi in response:
        name, city, description, duration = poi["name"], poi["city"], poi["description"], poi["duration"]
        res = execute(name)  # name是抽取的名称
        poi_name, poi_location, poi_id, city_code = parse_res(res)  # poi_name是检索到的真实名称
        if poi_name == "":
            continue
        time.sleep(1)
        poi_info_dict = {
            'name': name,
            'poi_name': poi_name,
            'location': poi_location,
            'id': poi_id,
            'city_code': city_code,
            'description': description,
            'duration': duration
        }
        res_list.append(poi_info_dict)
        print(poi_info_dict)
        print('='*20)
    return res_list

def search_again(arrange_route_v1):
    '''
        1. 搜索daily_plan_str中存在，但是poi_info_list中不存在的景点
        2、根据daily_plan_str的信息搜索每天的食宿
    '''
    arrange_route_v2 = arrange_route_v1.copy()
    for day, routes in arrange_route_v2.items():
        for i, route in enumerate(routes):
            start = route['start']
            start_location = start['location']
            if not start_location:
                res = execute(start['name'])  # name是锦艺那边抽取的名称
                print('end_name: ', start['name'])
                _, start_location, _, start_city_code = parse_res(res)
                # 更新起点信息
                route['start']['location'] = start_location
                route['start']['city_code'] = start_city_code
            print('start_location done')
            end = route['end']
            end_location = end['location']
            if not end_location:
                print('end_name: ', end['name'])
                res = execute(end['name'])  # name是抽取的名称
                _, end_location, _, end_city_code = parse_res(res)
                # 更新终点信息
                route['end']['location'] = end_location
                route['end']['city_code'] = end_city_code
            print('end_location done')
            # 更新routes中的route
            routes[i] = route
        # 更新arrange_route_v2中的routes
        arrange_route_v2[day] = routes

    return arrange_route_v2

def search_navi(arrange_route_v2):
    '''
        搜索路线
    '''
    arrange_route_v3 = arrange_route_v2.copy()
    for day, routes in arrange_route_v2.items():
        new_routes = []
        for i, route in enumerate(routes):
            start = route['start']
            end = route['end']
            start_location = start['location']
            start_city_code = start['city_code']
            end_location = end['location']
            end_city_code = end['city_code']
            if not start_location or not start_city_code or not end_location or not end_city_code:
                continue
            execute_navi_result = execute_navi(start_location, end_location, start_city_code, end_city_code)
            # 更新路线信息
            if execute_navi_result:
                duration, distance = execute_navi_result
                route['duration'] = duration
                route['distance'] = distance
            else:
                route['duration'] = 0
                route['distance'] = 0
            # 更新routes中的route
            new_routes.append(route)
        # 更新arrange_route_v3中的routes
        arrange_route_v3[day] = new_routes
    return arrange_route_v3


def check_search_again(arrange_route_v2):
    """检查并清理路线数据中location为空的路段

    Args:
        arrange_route_v2 (dict): 包含每日路线信息的字典

    Returns:
        dict: 清理后的路线数据
    """
    cleaned_routes = {}

    for day, routes in arrange_route_v2.items():
        # 过滤掉location为空的路段
        valid_routes = []
        for route in routes:
            if (route.get('start', {}).get('location') and
                route.get('end', {}).get('location')):
                valid_routes.append(route)

        if valid_routes:  # 只有当有效路段存在时才添加到结果中
            cleaned_routes[day] = valid_routes

    return cleaned_routes


def get_sys_prompt(context_data):
    sys_prompt = system_prompt.format(cluster_dict=context_data.tranform_clusters_to_markdown(),
                                      poi_info=context_data.tranform_to_markdown(),
                                      cur_arrangement=context_data.tranform_plans_to_markdown()
                                      )
    return sys_prompt

async def react_call_travel_plan(clustered_pois, city, start_time, end_time, day):
    max_round = 15
    round = 0

    context_data = ContextData(clustered_pois, start_time, end_time, day)

    is_finish = False

    msgs = Memory()
    sys_prompt = get_sys_prompt(context_data)
    logger.info(f"system prompt: {sys_prompt}")

    sys_msg = Message.system_message(content=sys_prompt)
    msgs.add_message(Message.user_message(content=first_user_prompt.format(city=city, start_time=start_time, end_time=end_time)))

    while round < max_round and is_finish == False:
        round += 1
        logger.info(f"Executing step {round}/{max_round}")

        should_act, cot, tool_call = await think_func(sys_msg, msgs)

        if not should_act:
            print("Thinking complete - no action needed")
            continue

        observation = act_fun(tool_call, context_data)
        logger.info(f"step {round}/{max_round} \n Observation: \n\n{observation}")

        # 创建工具消息并添加到消息历史
        for call in tool_call:
            tool_msg = Message.tool_message(
                content=observation,
                name=call.function.name,
                tool_call_id=call.id
            )
            msgs.add_message(tool_msg)

        if round == max_round:
            print(f"Reached max steps ({max_round})")

        # 遍历 toolcall 如果包含 final_answer 就终止
        for tool_call in tool_call:
            if tool_call.function.name == "final_answer":
                print("Final answer found")
                is_finish = True
                break
    return

def each_act_fun(name, args, my_data):
    logger.info(f"start action Tool name: {name}, arguments: {args}")
    # 根据不同的function name调用对应的工具函数
    if name == "arrange":
        print('执行arrange函数')
        poi_list = args.get("poi_list", [])
        print('poi_list: ', poi_list)
        day = args.get("day", 1)
        return arrange(poi_list, day, my_data)
    elif name == "adjust":
        new_poi_list = args.get("new_poi_list", [])
        day = args.get("day", 1)
        return adjust(new_poi_list, day, my_data)
    elif name == "search_for_poi":
        keyword = args.get("keyword", "")
        city_code = args.get("city_code", "")
        poi_type = args.get("poi_type", "")
        return search_for_poi(keyword, city_code, poi_type, my_data)
    elif name == "search_for_navi":
        poi_list = args.get("poi_list", [])
        day = args.get("day", 1)
        return search_for_navi(day, poi_list, my_data)
    elif name == "final_answer":
        return final_answer(my_data)
    else:
        return f"Error: Unknown function '{name}'"


def act_fun(tool_call, my_data):
    if not tool_call or not tool_call[0].function or not tool_call[0].function.name:
        return "Error: Invalid tool call format"

    ret_vec = []
    for call in tool_call:
        name = call.function.name
        args = json.loads(call.function.arguments or "{}")

        ret = each_act_fun(name, args, my_data)
        ret_vec.append(ret)

    return ret_vec[-1]

async def main(city: str, start_time: str, end_time: str):
    # 1. 根据输入query获取推荐的景区
    # [SCENE_START] 黄山 [SCENE_END]
    # TDOO 推荐点 [P1_START] 邯郸博物馆 [P1_END]
    # 输出 P1 P2 P3的景点
    # 计算旅行天数
    from datetime import datetime
    start_date = datetime.strptime(start_time, "%Y-%m-%d")
    end_date = datetime.strptime(end_time, "%Y-%m-%d")
    day = (end_date - start_date).days + 1  # 包含起始日期
    day = str(day)

    logger.info(f"旅行天数: {day}")

    recommend_scene_str, clusters_dict, index2poi = await get_recommend(city, day)
    # print('='*20)
    # print('clusters_dict: \n', clusters_dict)
    # print('='*20)
    #clusters_dict = {1: [{'name': '圆明园遗址公园', 'location': '116.300960,40.008759', 'id': 'B000A16E89', 'city_code': '010', 'opentime': '9:00-18:00', 'open_time_seconds': 32400, 'close_time_seconds': 64800, 'rating': '4.8', 'duration': 2.0, 'poi_index': 'P4'}, {'name': '颐和园', 'location': '116.275179,39.999617', 'id': 'B000A7O1CU', 'city_code': '010', 'opentime': '9:00-18:00', 'open_time_seconds': 32400, 'close_time_seconds': 64800, 'rating': '4.9', 'duration': 3.0, 'poi_index': 'P3'}], 2: [{'name': '国家体育场', 'location': '116.395866,39.993306', 'id': 'B000A7GWO5', 'city_code': '010', 'opentime': '9:00-18:00', 'open_time_seconds': 32400, 'close_time_seconds': 64800, 'rating': '4.9', 'duration': 1.0, 'poi_index': 'P5'}, {'name': '南锣鼓巷', 'location': '116.402394,39.937182', 'id': 'B0FFFAH7I9', 'city_code': '010', 'opentime': '9:00-18:00', 'open_time_seconds': 32400, 'close_time_seconds': 64800, 'rating': '4.8', 'duration': 1.0, 'poi_index': 'P7'}, {'name': '国家游泳中心', 'location': '116.390397,39.992834', 'id': 'B000A80ZU6', 'city_code': '010', 'opentime': '07:00-20:00', 'open_time_seconds': 25200, 'close_time_seconds': 72000, 'rating': '4.7', 'duration': 1.0, 'poi_index': 'P6'}, {'name': '什刹海', 'location': '116.385281,39.941862', 'id': 'B000A7O5PK', 'city_code': '010', 'opentime': '9:00-18:00', 'open_time_seconds': 32400, 'close_time_seconds': 64800, 'rating': '4.9', 'duration': 2.0, 'poi_index': 'P8'}], 3: [{'name': '天坛公园', 'location': '116.410829,39.881913', 'id': 'B000A81CB2', 'city_code': '010', 'opentime': '9:00-18:00', 'open_time_seconds': 32400, 'close_time_seconds': 64800, 'rating': '4.9', 'duration': 2.0, 'poi_index': 'P2'}, {'name': '故宫博物院', 'location': '116.397029,39.917839', 'id': 'B000A8UIN8', 'city_code': '010', 'opentime': '08:30-16:30', 'open_time_seconds': 30600, 'close_time_seconds': 59400, 'rating': '4.9', 'duration': 4.0, 'poi_index': 'P1'}]}
    #logger.info('clusters_dict: \n', clusters_dict)
    await react_call_travel_plan(clusters_dict, city, start_time, end_time, day)

    # 并行分支 2.1 使用prompt 抽取 json 的 poi名称，请求高德，返回给端上
    # 并行分支 2.2 使用景区请求 R1/V3 获取对应 每一天的行程安排，带时间和住宿
    # travel_plan_str = await get_travel_plan(city, recommend_scene_str, start_time, end_time, poi_info_list)
    # 3. TODO 删掉这个流程
    # 根据 分支 2.2 通过 prompt 抽取 json 的行程安排
    # daily_plan_str = get_daily_plan(travel_plan_str)

    # 并行分支 4.1 将每天的行程 返回给端上
    #format_to_show_json = format_show(daily_plan_str)

    # 4. 根据 分支 3 的行程安排，请求高德路线接口，获取路线结果
    # arrange_route = get_arrange_route(poi_info_list, daily_plan_str)
    # print('arrange_route')

    # 5. 路线结果格式化成返回给端上的格式
    #format_route_result = format_route(route_result)

    return

if __name__ == "__main__":
    city = "伊春"
    start_time = "2025-04-04"
    end_time = "2025-04-05"

    import asyncio
    asyncio.run(main(city, start_time, end_time))
