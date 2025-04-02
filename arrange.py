from typing import Dict, List
import asyncio
import aiohttp
import numpy as np
from sklearn.cluster import KMeans
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
from openai import OpenAI
from prompt import *
import json


'''
    简单版，没有分离景区和餐厅
    没有沿途搜
    排序的时候会参考距离矩阵
    暂时先用这一版


    推荐poi、聚类、排序、筛选、优化路线

'''


r1 = "deepseek-r1-250120"
v3 = "deepseek-v3-241226"


def call_llm(sys_prompt: str, query: str, request_model: str) -> str:
    #client = OpenAI(api_key="sk-ytpminknxtdkehuanngvpnnspxgfimhllugjqrywwysuknmj",
    #                base_url="https://api.siliconflow.cn/v1")

    client = OpenAI(api_key="cb9729a7-aa90-459f-8315-4ae41a6132f3",
                    base_url="https://ark.cn-beijing.volces.com/api/v3")

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

    ret = response.choices[0].message.content
    return ret

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

def parse_res(res, duration=None):
    '''
    解析高德地图API返回的POI信息
    '''
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

async def fetch_poi_info(session, poi: str, duration: float = None) -> Dict:
    '''
    异步获取单个POI的信息
    '''
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "keywords": poi,
        "key": '777e65792758b03da95607d112079834',
        "show_fields": "business,opentime_today,rating"
    }

    try:
        async with session.get(url, params=params) as response:
            result = await response.json()
            if result.get("status") == "1":
                return parse_res(result, duration)
            return {}
    except Exception:
        return {}

async def get_all_pois_info(poi_list: List[str]) -> List[Dict]:
    '''
    并发获取所有POI的信息
    '''
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_poi_info(session, poi) for poi in poi_list]
        return await asyncio.gather(*tasks)

def calculate_travel_time_matrix(pois: List[Dict]) -> np.ndarray:
    '''
    计算POI之间的行驶时间矩阵（示例：使用直线距离估算）
    实际应用中应该调用高德地图API获取真实行驶时间
    '''
    n = len(pois)
    matrix = np.zeros((n, n))
    for i in range(n):
        loc1 = np.array(list(map(float, pois[i]['location'].split(','))))
        for j in range(n):
            if i != j:
                loc2 = np.array(list(map(float, pois[j]['location'].split(','))))
                # 使用欧氏距离并假设平均速度60km/h来估算行驶时间（秒）
                distance = np.linalg.norm(loc1 - loc2)
                matrix[i][j] = distance * 100000 / 60  # 粗略估算行驶时间
    return matrix

def optimize_daily_route(daily_pois: List[Dict]) -> List[Dict]:
    '''
    使用TSP优化每天的游览路线
    1、target是总交通时间最短。
    2、约束条件是每个POI的访问时间在其营业时间内
    3、单日总时间不超过12小时
    '''
    if not daily_pois:
        return []

    # 计算行驶时间矩阵
    travel_time_matrix = calculate_travel_time_matrix(daily_pois)

    # 创建路由模型
    manager = pywrapcp.RoutingIndexManager(len(daily_pois), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    # 定义交通时间回调
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(travel_time_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # 添加时间维度，允许等待时间
    routing.AddDimension(
        transit_callback_index,
        60 * 60,  # 允许最多1小时的等待时间
        12 * 3600,  # 最大时间（12小时）
        False,  # 不从0开始累积
        'Time'
    )
    time_dimension = routing.GetDimensionOrDie('Time')

    # 添加时间窗口约束，增加灵活性
    for poi_idx in range(len(daily_pois)):
        index = manager.NodeToIndex(poi_idx)
        # 为每个POI设置更宽松的时间窗口
        open_time = daily_pois[poi_idx]['open_time_seconds']
        close_time = daily_pois[poi_idx]['close_time_seconds']
        # 确保时间窗口至少有2小时的间隔
        if close_time - open_time < 2 * 3600:
            close_time = open_time + 2 * 3600

        # 设置更合理的时间窗口范围
        earliest_time = max(9 * 3600, open_time)
        latest_time = min(18 * 3600, close_time)

        time_dimension.CumulVar(index).SetRange(
            earliest_time,
            latest_time
        )

        # 设置访问时长
        if poi_idx > 0:  # 跳过起点
            routing.AddToAssignment(time_dimension.SlackVar(index))

    # 求解
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    solution = routing.SolveWithParameters(search_parameters)

    # 解析结果
    ordered_pois = []
    if solution:
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            ordered_pois.append(daily_pois[node])
            index = solution.Value(routing.NextVar(index))

    return ordered_pois

def generate_timeline(ordered_pois: List[Dict], travel_time_matrix: np.ndarray) -> List[Dict]:
    '''
    生成详细的游览时间表
    '''
    timeline = []
    current_time = 8 * 3600  # 从8:00开始

    for i in range(len(ordered_pois)):
        poi = ordered_pois[i]
        # 计算到达时间
        travel_time = travel_time_matrix[i-1][i] if i > 0 else 0
        arrival_time = current_time + travel_time

        # 如果早于营业时间，等待开门
        if arrival_time < poi['open_time_seconds']:
            arrival_time = poi['open_time_seconds']

        # 计算离开时间
        departure_time = arrival_time + poi['duration'] * 3600

        # 格式化时间
        arrival_str = str(timedelta(seconds=int(arrival_time)))
        departure_str = str(timedelta(seconds=int(departure_time)))

        timeline.append({
            'poi': poi['name'],
            'arrival_time': arrival_str,
            'departure_time': departure_str,
            'duration': f"{poi['duration']}小时",
            'city_code': poi['city_code']
        })

        current_time = departure_time

    return timeline

def cluster_pois(poi_infos: List[Dict], n_clusters: int = 3) -> Dict[int, List[Dict]]:
    '''
    将POI聚类并返回按天分组的POI信息，每天游玩时间控制在8小时内
    '''
    # 提取有效的POI信息和位置
    valid_pois = []
    locations = []

    for poi in poi_infos:
        if poi and 'location' in poi:
            valid_pois.append(poi)
            lon, lat = map(float, poi['location'].split(','))
            locations.append([lon, lat])

    if not locations:
        return {}

    # 转换为numpy数组并聚类
    X = np.array(locations)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    cluster_labels = kmeans.fit_predict(X)

    # 按天分组POI信息
    daily_pois = {}
    for day in range(n_clusters):
        # 获取当天的POI列表
        day_pois = [valid_pois[i] for i in range(len(valid_pois))
                    if cluster_labels[i] == day]

        # 计算每个POI到其他POI的平均距离
        poi_distances = {}
        epsilon = 1e-10  # 添加一个小的epsilon值避免除零错误
        for i, poi1 in enumerate(day_pois):
            total_distance = 0
            count = 0
            loc1 = np.array(list(map(float, poi1['location'].split(','))))
            for j, poi2 in enumerate(day_pois):
                if i != j:
                    loc2 = np.array(list(map(float, poi2['location'].split(','))))
                    distance = np.linalg.norm(loc1 - loc2)
                    total_distance += distance
                    count += 1
            poi_distances[i] = total_distance / max(count, 1)  # 避免除以0

        # 计算距离的最大值，用于归一化，确保不会为0
        max_distance = max(max(poi_distances.values(), default=0), epsilon)

        # 按照评分/(时长*距离惩罚因子)比值降序排序
        # 距离惩罚因子 = 1 + 归一化距离，确保不会完全抵消评分的影响
        sort_weights = {}
        for idx, poi in enumerate(day_pois):
            distance = poi_distances[idx]
            rating = float(poi['rating'])
            duration = float(poi['duration'])
            sort_weights[poi['id']] = rating / (duration * (1 + distance / max_distance))

        # 使用预计算的排序权重进行排序
        day_pois.sort(key=lambda poi: sort_weights[poi['id']], reverse=True)
        # day_pois.sort(key=lambda x: float(x['rating'])/(float(x['duration'])*(1 + poi_distances[day_pois.index(x)]/max_distance)), reverse=True)

        # 筛选POI，确保总游玩时间不超过7小时
        selected_pois = []
        total_duration = 0
        for poi in day_pois:
            # 预估交通时间（假设每个景点间平均30分钟）
            transit_time = 0.5 if selected_pois else 0  # 小时
            if total_duration + float(poi['duration']) + transit_time <= 7:
                selected_pois.append(poi)
                total_duration += float(poi['duration']) + transit_time
            else:
                break

        if selected_pois:
            # 优化每天的游览路线
            optimized_pois = optimize_daily_route(selected_pois)  # selected_pois只是按照分数选择出满足游玩时间的poi，但是没有按照order
            if optimized_pois:
                # 生成时间表
                travel_time_matrix = calculate_travel_time_matrix(optimized_pois)
                timeline = generate_timeline(optimized_pois, travel_time_matrix)
                daily_pois[day + 1] = {'pois': optimized_pois, 'timeline': timeline}

    return daily_pois

async def main():
    # 示例POI列表
    # 每个元素格式：[景点名称, 游玩时长(小时)]
    fake_poi_list = [
        ['北京动物园', 3],
        ['鸟巢', 1],
        ['水立方', 1],
        ['奥森', 2],
        ['雍和宫', 1.5],
        ['圆明园', 2],
        ['地坛公园', 1.5],
        ['天安门', 1],
        ['王府井', 2],
        ['北海', 2],
        ['南锣鼓巷', 1.5],
        ['颐和园', 2],
        ['国家植物园', 1.5],
        ['什刹海', 2],
        ['香山', 3],
        ['故宫', 2.5],
        ['天坛公园', 2],
        ['前门', 2],
        ['国家博物馆', 2]
    ]

    # 获取所有POI信息
    poi_infos = await get_all_pois_info([poi[0] for poi in fake_poi_list])

    # 添加游玩时长信息
    for i, poi in enumerate(poi_infos):
        if poi:
            poi['duration'] = fake_poi_list[i][1]

    # 聚类并按天分组，同时优化每天的路线
    daily_schedule = cluster_pois(poi_infos)

    # 打印结果
    for day, schedule in daily_schedule.items():
        print('='*30)
        print(f'\n第{day}天游玩行程：')
        print('游览路线：')  # {"type": "景点", "名称": "颐和园", "游玩时长": "2"}
        query_list = []
        for poi in schedule['pois']:
            print(f"名称: {poi['name']}, 位置: {poi['location']}, "
                  f"营业时间: {poi['opentime']}, 评分: {poi['rating']}, "
                  f"游玩时长: {poi['duration']}小时, 城市代码: {poi['city_code']}")
            query_list.append({"type": "景点", "名称": poi['name'], "游玩时长": poi['duration'], "位置": poi['location']})
        # 调用大模型，推荐餐厅
        res = call_llm(PROMPT_RESTAURANT, f'城市: 北京\n景点观光路线信息: {query_list}', "deepseek-v3-241226")
        # 记录原始顺序
        poi_list = json.loads(res.strip().replace("'", '"'))

        # 处理餐厅POI的位置信息
        async def update_restaurant_locations(poi_list):
            async with aiohttp.ClientSession() as session:
                for poi in poi_list:
                    if poi.get('type') == '餐厅':
                        poi_info = await fetch_poi_info(session, poi['名称'])
                        if poi_info and 'location' in poi_info:
                            poi['位置'] = poi_info['location']

        # 更新餐厅位置信息
        await update_restaurant_locations(poi_list)
        # 计算相邻景点之间的路线和时间
        spot_routes = []
        for i in range(len(poi_list)-1):
            origin = poi_list[i]['位置']
            destination = poi_list[i+1]['位置']
            city1 = city2 = '010'  # 先固定为北京
            route_info = execute_navi(origin, destination, city1, city2)
            if route_info:
                spot_routes.append({
                    'start': poi_list[i],
                    'end': poi_list[i+1],
                    'duration': route_info[0],
                    'distance': route_info[1]
                })
        print('spot_routes:\n', spot_routes)



if __name__ == '__main__':
    asyncio.run(main())

