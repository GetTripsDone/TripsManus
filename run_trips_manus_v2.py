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
    poi_list = []
    async for section in call_llm("", prompt, v3):
        sections.append(section)
        # 这里你可以对每个section立即进行处理
        print(f"收到新的景点信息:\n{section}\n")

        # TODO 请求对应的poi，返回结果

        # excecuse =
        # TODO 调用poi接口，返回结果
        # print()
        # poi_list.append(excecuse)

    return "\n".join(sections)

async def get_travel_plan(city: str, recommend_scene_str: str, start_time:str, end_time:str) -> str:
    global r1, v3
    prompt = f"""
    用户已经在{city}，根据如下提供的景点信息，规划一个从{start_time}到{end_time}时间的行程。
    包含餐饮和住宿，餐饮和住宿不用给出具体点，给出在什么位置进行餐饮和住宿即可。
    包含详细的时间安排和餐饮酒店住宿。你需要考虑一下各个地点之间的路线、距离和时间

    # ** 注意 **
    1.  输出采用markdown格式，每一天的行程安排都用分割线进行分割，第一天的输出前面也要加分割线
    2.  游玩的景区，需要加入  [PX_START] 景点名称 [PX_END]，X是景点编号
    3.  早/中/晚吃饭的地方，需要加入 [Restaurant_start] 餐馆描述 [Restaurant_End]
    4. 晚上住宿的地方，需要加入 [Hotel_Start] 酒店 [Hotel_End]

    """ + recommend_scene_str

    sections = []
    async for section in call_llm("", prompt, v3):
        sections.append(section)
        # 这里你可以对每个section立即进行处理
        print(f"收到新的行程信息:\n{section}\n")

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
        time.sleep(0.5)
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

def get_arrange_route(poi_info_list, daily_plan_str):
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
    recommend_scene_str = await get_recommend(city)
    # 并行分支 2.1 使用prompt 抽取 json 的 poi名称，请求高德，返回给端上
    #poi_info_list = extract_search_poi(recommend_scene_str)
    # 并行分支 2.2 使用景区请求 R1/V3 获取对应 每一天的行程安排，带时间和住宿
    travel_plan_str = await get_travel_plan(city, recommend_scene_str, start_time, end_time)
    # 3. TODO 删掉这个流程
    # 根据 分支 2.2 通过 prompt 抽取 json 的行程安排
    # daily_plan_str = get_daily_plan(travel_plan_str)

    # 并行分支 4.1 将每天的行程 返回给端上
    #format_to_show_json = format_show(daily_plan_str)

    # 4. 根据 分支 3 的行程安排，请求高德路线接口，获取路线结果
    # arrange_route_str = get_arrange_route(poi_info_list, daily_plan_str)

    # 5. 路线结果格式化成返回给端上的格式
    #format_route_result = format_route(route_result)

    return

if __name__ == "__main__":
    city = "黄山"
    start_time = "2025-03-10"
    end_time = "2025-03-13"

    import asyncio
    asyncio.run(main(city, start_time, end_time))

    poi_info_list = [{'name': '张掖丹霞国家地质公园', 'poi_name': '张掖世界地质公园', 'location': '100.042200,38.975330', 'id': 'B03A813VVF', 'city_code': '0936', 'description': '以其色彩斑斓的丹霞地貌著称，是摄影爱好者的天堂。', 'duration': '3.5'}, {'name': '鸣沙山月牙泉', 'poi_name': '鸣沙山月牙泉', 'location': '94.680396,40.088833', 'id': 'B03A9000ZN', 'city_code': '0937', 'description': '沙漠与清泉共存的奇观，可以体验骑骆驼和滑沙。', 'duration': '2.5'}, {'name': '麦积山石窟', 'poi_name': '麦积山石窟', 'location': '106.008075,34.350764', 'id': 'B03AA005RW', 'city_code': '0938', 'description': '以精美的泥塑艺术闻名，是中国四大石窟之一。', 'duration': '2.5'}, {'name': '莫高窟', 'poi_name': '莫高窟景区', 'location': '94.809374,40.042511', 'id': 'B03A900102', 'city_code': '0937', 'description': '世界文化遗产，拥有丰富的佛教艺术壁画和雕塑。', 'duration': '3.5'}, {'name': '嘉峪关关城', 'poi_name': '嘉峪关文物景区', 'location': '98.228494,39.801021', 'id': 'B079100049', 'city_code': '1937', 'description': '明代万里长城的西端起点，被判为“天下第一雄关”。', 'duration': '2.5'}, {'name': '拉卜楞寺', 'poi_name': '拉卜楞寺', 'location': '102.509660,35.192953', 'id': 'B03AD001JE', 'city_code': '0941', 'description': '藏传佛教格鲁派六大寺院之一，拥有丰富的宗教文化和建筑艺术。', 'duration': '2.5'}, {'name': '郎木寺', 'poi_name': '郎木寺院', 'location': '102.632929,34.092557', 'id': 'B03AD009J5', 'city_code': '0941', 'description': '藏传佛教寺院，周围风景优美，是体验藏族文化的好去处。', 'duration': '2.5'}, {'name': '夏河桑科草原', 'poi_name': '桑科草原', 'location': '102.434001,35.110502', 'id': 'B0HR2ZSWZL', 'city_code': '0941', 'description': '广阔的草原风光，可以体验骑马和藏族民俗活动。', 'duration': '3.5'}, {'name': '临夏八坊十三巷', 'poi_name': '八坊十三巷', 'location': '103.210271,35.591251', 'id': 'B0FFIK006P', 'city_code': '0930', 'description': '回族文化街区，充满了浓郁的民族风情和历史文化。', 'duration': '2.5'}, {'name': '黄河石林', 'poi_name': '黄河石林国家地质公园', 'location': '104.314490,36.892922', 'id': 'B03AF002D7', 'city_code': '0943', 'description': '以奇特的石林地貌和黄河风光相结合，景色壮丽。', 'duration': '3.5'}, {'name': '崆峒山', 'poi_name': '崆峒山风景名胜区', 'location': '106.530016,35.547444', 'id': 'B03A500C84', 'city_code': '0933', 'description': '道教名山，风景秀丽，文化底蕴深厚。', 'duration': '3.5'}, {'name': '马蹄寺', 'poi_name': '马蹄生态文化旅游区', 'location': '100.416624,38.484258', 'id': 'B03A8005PU', 'city_code': '0936', 'description': '集石窟艺术、祁连山风光和裕固族风情于一体的旅游景区。', 'duration': '2.5'}]

    daily_plan_str = {
    "day1": {
        "title": "敦煌文化+沙漠奇观",
        "topic": "佛教艺术与沙漠体验",
        "lodging": "敦煌市区",
        "restaurant": "敦煌市区（早/午/晚）",
        "travel_details": [
            {
                "time": "07:00-08:00",
                "description": "早餐（敦煌市区，推荐牛肉面、杏皮水）"
            },
            {
                "time": "08:30-12:30",
                "description": "莫高窟（历史文化）<br>参观洞窟壁画，需提前预约门票。"
            },
            {
                "time": "12:30-13:30",
                "description": "午餐（景区附近简餐或返回市区品尝驴肉黄面）"
            },
            {
                "time": "14:00-17:30",
                "description": "鸣沙山月牙泉（自然风光）<br>骑骆驼、滑沙，傍晚光线适合摄影。"
            },
            {
                "time": "18:00-19:00",
                "description": "晚餐（市区内，尝试敦煌酿皮、烤羊排）"
            }
        ],
        "routes": [
            {
                "start": "敦煌市区早餐店，(推荐牛肉面、杏皮水）",
                "end": "莫高窟",
                "Transportation": "汽车"
            },
            {
                "start": "莫高窟",
                "end": "午餐店（莫高窟景区附近简餐)",
                "Transportation": "汽车"
            },
            {
                "start": "午餐店（莫高窟景区附近简餐)",
                "end": "鸣沙山月牙泉",
                "Transportation": "汽车"
            },
            {
                "start": "鸣沙山月牙泉",
                "end": "晚餐店（敦煌市区内 尝试敦煌酿皮、烤羊排）",
                "Transportation": "汽车"
            }
        ]
    },
    "day2": {
        "title": "雄关漫道+丹霞日落",
        "topic": "长城文化与地质奇观",
        "lodging": "张掖市区",
        "restaurant": "嘉峪关市区（午）、张掖市区（晚）",
        "travel_details": [
            {
                "time": "07:00-07:30",
                "description": "早餐后退房，前往敦煌高铁站"
            },
            {
                "time": "08:00-12:00",
                "description": "高铁前往嘉峪关（约4小时）"
            },
            {
                "time": "12:00-13:00",
                "description": "午餐（嘉峪关市区，推荐羊肉垫卷子）"
            },
            {
                "time": "13:30-16:00",
                "description": "嘉峪关关城（历史文化）<br>登城楼俯瞰戈壁，感受“天下第一雄关”气势。"
            },
            {
                "time": "16:30-18:30",
                "description": "高铁前往张掖（约2小时）"
            },
            {
                "time": "19:00-20:00",
                "description": "晚餐（张掖市区，推荐搓鱼面、炒拨拉）"
            }
        ],
        "routes": [
            {
                "start": "敦煌市区早餐店",
                "end": "敦煌高铁站",
                "Transportation": "汽车"
            },
            {
                "start": "敦煌高铁站",
                "end": "嘉峪关",
                "Transportation": "高铁"
            },
            {
                "start": "午餐店（嘉峪关市区，推荐羊肉垫卷子）",
                "end": "嘉峪关关城",
                "Transportation": "汽车"
            },
            {
                "start": "嘉峪关关城",
                "end": "嘉峪关高铁站",
                "Transportation": "汽车"
            },
            {
                "start": "嘉峪关高铁站",
                "end": "张掖",
                "Transportation": "高铁"
            },
            {
                "start": "张掖高铁站",
                "end": "晚餐店（张掖市区，推荐搓鱼面、炒拨拉）",
                "Transportation": "汽车"
            }
        ]
    },
    "day3": {
        "title": "丹霞地貌+石窟探秘",
        "topic": "自然奇观与民族风情",
        "lodging": "张掖市区",
        "restaurant": "丹霞景区附近（午）、张掖市区（晚）",
        "travel_details": [
            {
                "time": "07:00-07:30",
                "description": "早餐（张掖市区）"
            },
            {
                "time": "08:00-12:00",
                "description": "张掖丹霞国家地质公园（自然风光）<br>清晨色彩最艳丽，适合航拍。"
            },
            {
                "time": "12:30-13:30",
                "description": "午餐（景区附近农家菜或返回市区）"
            },
            {
                "time": "14:00-17:00",
                "description": "马蹄寺（民俗风情）<br>探访悬崖石窟，体验裕固族文化。"
            },
            {
                "time": "17:30-18:30",
                "description": "返回张掖市区，晚餐（推荐手抓羊肉、灰豆汤）"
            }
        ],
        "routes": [
            {
                "start": "张掖市区早餐店",
                "end": "张掖丹霞国家地质公园",
                "Transportation": "汽车"
            },
            {
                "start": "张掖丹霞国家地质公园",
                "end": "午餐（张掖市区寻找）",
                "Transportation": "汽车"
            },
            {
                "start": "午餐（张掖市区寻找）",
                "end": "马蹄寺",
                "Transportation": "汽车"
            },
            {
                "start": "马蹄寺",
                "end": "张掖市区，晚餐（推荐手抓羊肉、灰豆汤）",
                "Transportation": "汽车"
            }
        ]
    }
}
    #arrange_route_str = get_arrange_route(poi_info_list, json.dumps(daily_plan_str, ensure_ascii=False))

