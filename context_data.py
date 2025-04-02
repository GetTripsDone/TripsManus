import os
from re import L
import sys
import time
import json
from typing import Dict, List
from pydantic import BaseModel, Field

class POI(BaseModel):
    """Represents a point of interest."""
    id: str
    name: str
    description: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    category: str = ""
    rating: float = 0.0
    price: float = 0.0
    address: str = ""
    phone: str = ""
    website: str = ""
    opening_hours: str
    image: str = ""
    duration: float

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "opening_hours": self.opening_hours,
            "duration": self.duration
        }

    def to_json(self):
        return json.dumps(self.to_dict())

class Route(BaseModel):
    """Represents a route."""
    id: str
    start_time: str
    end_time: str
    start_point: str
    end_point: str

    # 初始化函数
    def __init__(self, start_point, end_point):
        self.start_point = start_point
        self.end_point = end_point

    # 转换为字典的函数
    def to_dict(self):
        return {
            "start_point": self.start_point.to_dict(),
            "end_point": self.end_point.to_dict()
        }

class DayPlan(BaseModel):
    """Represents a day plan."""
    start_time: str
    end_time: str
    travel_list: List[str]
    route: List[Route]

    # 初始化函数
    def __init__(self, start_time, travel_list):
        self.start_time = start_time
        self.travel_list = travel_list

    # 转换为字典的函数
    def to_dict(self):
        return {
            "start_time": self.start_time,
            "travel_list": [poi.to_dict() for poi in self.travel_list]
        }

class ContextData:
    # {"P1": POI, "P2": POI ...}
    pois: dict = {}
    # {"H1": POI, "H2": POI ...}
    hotels: dict = {}
    # {"R1": POI, "R2": POI...}
    restaurants: dict = {}
    # {"C1": [P1, P2...], ...}
    clusters: dict = {}

    # {"day1": {"start_time": "2021-01-01 00:00:00",
    #           "travel_list" : [P1, P2...],
    #           "route": [{"start_point": P1,
    #                      "end_point": P2},
    #                     ...]
    #   },
    # {}...}
    plans: dict = {}

    def __init__(self, cluster_dict: Dict[int, List[Dict]]):
        poi_idx_cnt = 1

        for cluster_id, poi_list in cluster_dict.items():
            self.clusters[cluster_id] = []

            for poi in poi_list:
                poi_id = f"P{poi_idx_cnt}"
                curr_poi = POI(
                    id=poi_id,
                    name=poi["name"],
                    opening_hours=poi["opentime"],
                    duration=poi["duration"]
                )

                self.pois[poi_id] = curr_poi
                self.clusters[cluster_id].append(poi_id)
                poi_idx_cnt += 1

        return

    arrange_ment: dict = {}

    poi_index: int = 0
    hotel_index: int = 0
    restaurant_index: int = 0

    # 将 pois 转换为 markdown 的函数
    def tranform_pois_to_markdown(self):
        """Transform pois to markdown."""
        markdown = ""
        if len(self.pois) == 0:
            return "### 注意 ###\n -当前暂时未收集到景点POI信息\n\n"

        for idx, (poi_id, poi) in enumerate(self.pois.items(), 1):
            markdown += f"### {poi_id}. {poi.name}\n"
            markdown += f"**地址：**{poi.address}\n"
            markdown += f"**开放时间：**{poi.opening_hours}\n"
            # 游玩时长
            markdown += f"**游玩时长：**{poi.duration}小时\n"
            markdown += "---\n"  # 添加分隔线

        return markdown

    # 将 hotels 转换为 markdown 的函数
    def tranform_hotels_to_markdown(self):
        """Transform hotels to markdown."""
        markdown = ""
        if len(self.hotels) == 0:
            return "### 注意 ###\n -当前暂时未收集到酒店POI信息\n\n"

        for idx, (hotel_id, hotel) in enumerate(self.hotels.items(), 1):
            markdown += f"### {hotel_id}. {hotel.name}\n"
            markdown += f"**地址：**{hotel.address}\n"
            markdown += f"**开放时间：**{hotel.opening_hours}\n"
            markdown += "---\n"  # 添加分隔线
        return markdown

    # 将 restaurants 转换为 markdown 的函数
    def tranform_restaurants_to_markdown(self):
        """Transform restaurants to markdown."""
        markdown = ""
        if len(self.restaurants) == 0:
            return "### 注意 ###\n -当前暂时未收集到餐厅POI信息\n\n"

        for idx, (restaurant_id, restaurant) in enumerate(self.restaurants.items(), 1):
            markdown += f"### {restaurant_id}. {restaurant.name}\n"
            markdown += f"**地址：**{restaurant.address}\n"
            markdown += f"**开放时间：**{restaurant.opening_hours}\n"
            markdown += "---\n"  # 添加分隔线
        return markdown

    def tranform_to_markdown(self):
        """Transform to markdown."""
        markdown = ""
        markdown += self.tranform_pois_to_markdown()
        markdown += self.tranform_hotels_to_markdown()
        markdown += self.tranform_restaurants_to_markdown()

        return markdown

    # 将 clusters 转换为 markdown 的函数
    def tranform_clusters_to_markdown(self):
        """Transform clusters to markdown."""
        markdown = ""

        # cluster 是一个poi列表，需要把他们的id打印成一行
        for idx, (cluster_id, cluster) in enumerate(self.clusters.items(), 1):
            markdown += f"### ** 地点聚类 ** C{cluster_id}.\n"
            for poi in cluster:
                markdown += f"{poi} "
            markdown += "\n"
            markdown += "---\n"  # 添加分隔线

        return markdown

    # 将 plans 转换为 markdown 的函数
    def tranform_plans_to_markdown(self):
        """Transform plans to markdown."""
        markdown = ""
        if len(self.plans) == 0:
            return "### 注意 ###\n -当前暂时未收集到行程信息\n\n"

        # plan是一个数据结构
        for idx, plan in enumerate(self.plans.items()):
            markdown += f"### Day {idx}\n"
            markdown += f"**今天出发时间：**{plan.start_time}\n"
            markdown += "**依次要经过的POI点：**\n"
            for poi in plan.travel_list:
                markdown += f"- ID:{poi}\n"
            markdown += "**路线：**\n"
            for route in plan.route:
                markdown += f"- 从{route.start_point}到{route.end_point}\n"

            markdown += "---\n"  # 添加分隔线

        return markdown


