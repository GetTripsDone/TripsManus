import os
import sys
import json
from openai import OpenAI
from typing import Dict, Optional
import requests
import time
from app.tool import arrange_days
from local_prompt import Daily_Plan_SysPrompt, Daily_Plan_UserPrompt, PROMPT_JSON, mock_input_text, PROMPT_COMBINE

r1 = "deepseek-ai/DeepSeek-R1"
v3 = "deepseek-ai/DeepSeek-V3"

def call_llm(sys_prompt: str, query: str, request_model: str) -> str:
    client = OpenAI(api_key="sk-ytpminknxtdkehuanngvpnnspxgfimhllugjqrywwysuknmj",
                    base_url="https://api.siliconflow.cn/v1")

    if sys_prompt == "":
        response = client.chat.completions.create(
                model= request_model,
                messages=[
                    {"role": "user", "content": query},
                ],

                stream=False,
                temperature=1.0,
        )
    else:
        response = client.chat.completions.create(
                model= request_model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": query},
                ],

                stream=False,
                temperature=1.0,
        )

    #print(f"llm response is {response}")
    #print(f"llm response content is {response.choices[0].message}")

    # message 数据结构
    # reasoning_content (r1 独有)
    # content role annotations audio
    # refusal function_call tool_calls

    ret = response.choices[0].message.content
    return ret

def get_recommend(city: str):
    global v3
    prompt = f"""
    推荐尽可能多的{city}值得一去的景点
    输入格式是markdown：

    # 类别1
    1. 景点名称
     - 所在地点
     - 景点介绍
     - 预估游玩时长
    ...
    """

    recommend_scene_str = call_llm("", prompt, v3)

    print(f"In Recommend:\n{recommend_scene_str}")

    return recommend_scene_str

def get_travel_plan(recommend_scene_str: str, start_time:str, end_time:str) -> str:
    global r1
    prompt = f"""
    根据如下提供的景点信息，规划一个从{start_time}到{end_time}时间的行程。
    包含餐饮和住宿，餐饮和住宿不用给出具体点，给出在什么位置进行餐饮和住宿即可。
    包含详细的时间安排。\n""" + recommend_scene_str

    travel_plan_str = call_llm("", prompt, r1)

    print(f"In Travel Plan:\n{travel_plan_str}")

    return travel_plan_str

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
        result = response.json()
        if result.get("status") == "1":
            return result
        else:
            return {"error": f"搜索失败: {result.get('info')}"}
    except Exception as e:
        return {"error": f"请求失败: {str(e)}"}

def parse_res(res):
    result = res['pois'][0]
    poi_name = result['name']
    poi_location = result['location']
    poi_id = result['id']
    city_code = result['citycode']
    return poi_name, poi_location, poi_id, city_code

def extract_search_poi(recommend_scene_str):
    response = call_llm(PROMPT_JSON, mock_input_text, v3)
    response = json.loads(response)
    # [{"name": "故宫博物院", "city": "北京", "description": "明清两代皇家宫殿建筑群，世界文化遗产", "duration": "3.5"},
    #  {"name": "天坛公园", "city": "北京", "description": "明清皇帝祭天祈谷的祭坛建筑群", "duration": "2.5"},
    # {"name":"八达岭长城", "city": "北京", "description": "保存最完好的明长城精华段", "duration": "5"}]
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

def get_arrange_route(poi_info_list, daily_plan_str):
    '''
        1、搜索daily_plan_str中存在，但是poi_info_list中不存在的景点
        2、根据daily_plan_str的信息搜索每天的食宿
        3、根据以上结果搜索路线
        poi_info_list: {"name":"八达岭长城", "city": "北京", "description": "保存最完好的明长城精华段", "duration": "5"}
    '''

    daily_plan = json.loads(daily_plan_str)
    # {day1: {routes: [{start, end, Transportation}, {start, end, Transportation}, ...]}, day2: {routes: [{start, end, Transportation}, {start, end, Transportation}, ...]}}
    simplify_plan = {}
    for day, value in daily_plan.items():
        routes = value['routes']  # list
        simplify_plan[day] = routes  # [{start, end, Transportation}, {start, end, Transportation}, ...]



def main(city: str, start_time: str, end_time: str):
    # 1. 根据输入query获取推荐的景区
    recommend_scene_str = get_recommend(city)
    # 并行分支 2.1 使用prompt 抽取 json 的 poi名称，请求高德，返回给端上
    # poi_info_list = extract_search_poi(recommend_scene_str)
    # 并行分支 2.2 使用景区请求 R1 获取对应 每一天的行程安排，带时间和住宿
    travel_plan_str = get_travel_plan(recommend_scene_str, start_time, end_time)
    # 3.
    # 根据 分支 2.2 通过 prompt 抽取 json 的行程安排
    daily_plan_str = get_daily_plan(travel_plan_str)

    # 并行分支 4.1 将每天的行程 返回给端上
    #format_to_show_json = format_show(daily_plan_str)

    # 4. 根据 分支 3 的行程安排，请求高德路线接口，获取路线结果
    # arrange_route_str = get_arrange_route(poi_info_list, daily_plan_str)

    # 5. 路线结果格式化成返回给端上的格式
    #format_route_result = format_route(route_result)

    return

if __name__ == "__main__":
    city = "上海"
    start_time = "2025-03-10"
    end_time = "2025-03-13"

    main(city, start_time, end_time)

