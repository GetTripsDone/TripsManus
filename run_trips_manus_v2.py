import os
import sys
import json
from openai import OpenAI
from typing import Dict, Optional
import requests
import time
from app.tool import arrange_days
from local_prompt import Daily_Plan_SysPrompt, Daily_Plan_UserPrompt, PROMPT_JSON, mock_input_text, PROMPT_COMBINE, recomend_scence_str_mock, arrange_route_str_mock

#r1 = "deepseek-ai/DeepSeek-R1"
#v3 = "deepseek-ai/DeepSeek-V3"

r1 = "deepseek-r1-250120"
v3 = "deepseek-v3-241226"

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


async def get_recommend(city: str):
    global v3
    prompt = f"""
    推荐尽可能多的{city}值得一去的景点

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
    async for section in call_llm("", prompt, v3):

        # 解析每个section,得到提取的poi name, poi_index(p1, p2, p3....)
        poi_name, poi_index = parse_poi_section(section)
        if not poi_name:
            continue
        sections.append(section)
        print(f"收到新的景点信息:\n{section}\n")
        # 请求对应的poi，返回结果
        poi_name, poi_location, poi_id, city_code = parse_res(execute(poi_name))  # poi_name是检索到的真实名称
        time.sleep(1)
        poi_info_dict = {
            'poi_index': poi_index,
            'poi_name': poi_name,
            'location': poi_location,
            'id': poi_id,
            'city_code': city_code
        }
        poi_info_list.append(poi_info_dict)
        print(f"收到新的POI检索信息:\n{poi_info_dict}\n")

    return "\n".join(sections), poi_info_list


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
    poi_dict = {str(poi['poi_index']): poi for poi in poi_info_list}

    # 提取所有标记对之间的内容
    arranged_pois = []
    pattern = r'\[(P\d+|RESTAURANT|HOTEL)_(?:START|END)\]([^\[]+)'
    # pattern = r'\[(P\d+|Restaurant|Hotel)_(?:START|END|start|end)\]\s*([^\[]+?)\s*\[(P\d+|Restaurant|Hotel)_(?:START|END|start|end)\]'

    # 按顺序找出所有匹配项
    import re
    daily_plan_str = daily_plan_str.replace('_End', '_END').replace('_Start', '_START').replace('_start', '_START').replace('_end', '_END')
    matches = re.finditer(pattern, daily_plan_str)
    current_poi = None

    for match in matches:
        marker_type = match.group(1)  # P1, P2, Restaurant, Hotel等
        # print('marker_type:\n', marker_type)
        poi_name = match.group(2).strip()

        # 如果是START标记，处理POI信息
        if '_START' in match.group(0):
            if marker_type.startswith('P'):
                # 对于Px类型的POI，从poi_info_list中查找
                poi_index = marker_type
                found = False
                for poi_info in poi_info_list:
                    if poi_info['poi_index'] == poi_index:
                        current_poi = poi_info.copy()
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
                        'city_code': poi_info[3]
                    }
            else:
                # 对于Restaurant和Hotel类型，直接搜索
                # print('marker_type:\n', marker_type)
                # print('poi_name:\n', poi_name)
                poi_info = parse_res(execute(poi_name)) if poi_name else ('', '', '', '')
                current_poi = {
                    'poi_index': marker_type.lower(),
                    'poi_name': poi_name,
                    'location': poi_info[1],
                    'id': poi_info[2],
                    'city_code': poi_info[3]
                }

        # 如果是END标记且有当前POI，添加到列表中
        elif '_END' in match.group(0) and current_poi:
            arranged_pois.append(current_poi)
            current_poi = None

    # 过滤掉location、id和city_code都为空的POI
    arranged_pois = [poi for poi in arranged_pois if not (poi['location'] == '' or poi['city_code'] == '')]
    return arranged_pois


async def get_travel_plan(city: str, recommend_scene_str: str, start_time:str, end_time:str, poi_info_list:list) -> str:
    global r1, v3
    prompt = f"""
    用户已经在{city}，根据如下提供的景点信息，规划一个从{start_time}到{end_time}时间的行程。
    包含餐饮和住宿，餐饮和住宿不用给出具体点，给出在什么位置进行餐饮和住宿即可。
    包含详细的时间安排和餐饮酒店住宿。你需要考虑一下各个地点之间的路线、距离和时间

    # ** 注意 **
    1.  输出采用markdown格式，每一天的行程安排都用分割线进行分割，第一天的输出前面也要加分割线
    2.  游玩的景区，需要加入 前后缀 [PX_START] 景点名称 [PX_END]，X是景点编号
    3.  早/中/晚吃饭的地方，需要加入 前后缀 [RESTAURANT_START] 餐馆名称描述 [RESTAURANT_END]
    4.  晚上住宿的地方，需要加入 前后缀 [HOTEL_START] 酒店名称描述 [HOTEL_END]
    5.  餐馆名称和酒店名称的所有信息，请统一输出在 前后缀 内部
    """ + recommend_scene_str

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


def parse_res(res):
    result = res['pois']
    if not result:
        return '', '', '', ''
    result = result[0]
    poi_name = result['name']
    poi_location = result['location']
    poi_id = result['id']
    city_code = result['citycode']
    return poi_name, poi_location, poi_id, city_code

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

def _get_arrange_route(poi_info_list, daily_plan_str):
    '''
        1、搜索daily_plan_str中存在，但是poi_info_list中不存在的景点
        2、根据daily_plan_str的信息搜索每天的食宿
        3、根据以上结果搜索路线
    '''

    daily_plan = json.loads(daily_plan_str)
    # {day1: {routes: [{start, end, Transportation}, {start, end, Transportation}, ...]}, day2: {routes: [{start, end, Transportation}, {start, end, Transportation}, ...]}}
    # 简化plan的格式
    simplify_plan = {}
    for day, value in daily_plan.items():
        routes = value['routes']  # list
        simplify_plan[day] = routes  # [{start, end, Transportation}, {start, end, Transportation}, ...]
    # 使用PROMPT_COMBINE作为系统提示词，并代入实际参数
    prompt = PROMPT_COMBINE.replace('{simplify_plan}', json.dumps(simplify_plan, ensure_ascii=False)).replace('{poi_info_list}', json.dumps(poi_info_list, ensure_ascii=False))
    print('sty play the game')
    # 调用r1模型生成路线安排结果
    global v3
    arrange_route_str = call_llm("", prompt, v3)
    if "```json" in arrange_route_str and "```" in arrange_route_str:
        arrange_route_str = arrange_route_str.split("```json")[1].split("```")[0]
    print(f"prompt result arrange route {arrange_route_str}")

    # print('='*20)
    arrange_route_v1 = json.loads(arrange_route_str)
    # arrange_route_v1 = json.loads(arrange_route_str_mock)  # mock数据
    print(f"json result arrange route {arrange_route_v1}")
    print('='*20)
    # 重新搜索没搜到的点
    arrange_route_v2 = search_again(arrange_route_v1)
    arrange_route_v2 = check_search_again(arrange_route_v2)  # 校验格式
    print(f"the final route with location {arrange_route_v2}")

    # 搜路逻辑暂时不要
    # print('='*20)
    # # 搜路返回结果
    # arrange_route_v3 = search_navi(arrange_route_v2)
    # print(arrange_route_v3)
    # print('='*20)
    # arrange_route_str = json.dumps(arrange_route_v3, ensure_ascii=False)
    return arrange_route_v2

async def main(city: str, start_time: str, end_time: str):
    # 1. 根据输入query获取推荐的景区
    # [SCENE_START] 黄山 [SCENE_END]
    # TDOO 推荐点 [P1_START] 邯郸博物馆 [P1_END]
    # 输出 P1 P2 P3的景点
    recommend_scene_str, poi_info_list = await get_recommend(city)
    # 并行分支 2.1 使用prompt 抽取 json 的 poi名称，请求高德，返回给端上
    # 并行分支 2.2 使用景区请求 R1/V3 获取对应 每一天的行程安排，带时间和住宿
    travel_plan_str = await get_travel_plan(city, recommend_scene_str, start_time, end_time, poi_info_list)
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
    city = "北京"
    start_time = "2025-03-24"
    end_time = "2025-03-27"

    import asyncio
    asyncio.run(main(city, start_time, end_time))
