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
from context_data import ContextData, DayPlan, POI, Route
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime, timedelta


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



