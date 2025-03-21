import os
import sys
import json
from openai import OpenAI
from local_prompt import Daily_Plan_SysPrompt, Daily_Plan_UserPrompt

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

    ret = ""

    if request_model == r1:
        ret = response.choices[0].message.reasoning_content
    else:
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
    global r1
    prompt = Daily_Plan_UserPrompt + travel_plan_str

    daily_plan_str = call_llm(Daily_Plan_SysPrompt, prompt, v3)

    print(f"In Daily Plan:\n{daily_plan_str}")
    return daily_plan_str

def main(city: str, start_time: str, end_time: str):
    # 1. 根据输入query获取推荐的景区
    recommend_scene_str = get_recommend(city)
    # 并行分支 2.1 使用prompt 抽取 json 的 poi名称，请求高德，返回给端上

    # 并行分支 2.2 使用景区请求 R1 获取对应 每一天的行程安排，带时间和住宿
    travel_plan_str = get_travel_plan(recommend_scene_str, start_time, end_time)
    # 3.
    # 根据 分支 2.2 通过 prompt 抽取 json 的行程安排
    daily_plan_str = get_daily_plan(travel_plan_str)
    # 并行分支 4.1 将每天的行程 返回给端上
    format_to_show_json = format_show(daily_plan_str)
    # 并行分支 4.2 请求高德路线接口，获取路线结果，返回给端上呈现
    route_result = get_route_result(daily_plan_str)
    # 5. 路线结果格式化成返回给端上的格式
    format_route_result = format_route(route_result)

    return

if __name__ == "__main__":
    city = "北京"
    start_time = "2025-03-10"
    end_time = "2025-03-13"

    main(city, start_time, end_time)

