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
    location: str = ""
    city_code: str = ""
    category: str = ""
    rating: str = "4.5"
    price: float = 0.0
    address: str = ""
    phone: str = ""
    website: str = ""
    opening_hours: str
    opentime: str = ""
    open_time_seconds: int = 0
    close_time_seconds: int = 0
    image: str = ""
    duration: float = 1.0
    poi_index: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "opening_hours": self.opening_hours,
            "duration": self.duration
        }

    def to_poi_dict(self):
        return {
            'name': self.name,
            'location': f"{self.longitude},{self.latitude}",
            'id': self.id,
            'citycode': self.city_code,
            'opentime': self.opentime,
            'rating': str(self.rating),
            'duration': self.duration,
            'open_time_seconds': self.open_time_seconds,
            'close_time_seconds': self.close_time_seconds,
            'poi_index': self.poi_index
        }

    def to_json(self):
        return json.dumps(self.to_dict())

class Route(BaseModel):
    """Represents a route."""
    id: str = ""
    start_time: str = ""
    end_time: str = ""
    start_point: POI
    end_point: POI

    class Config:
        arbitrary_types_allowed = True

    def to_dict(self):
        return {
            "start_point": self.start_point.to_dict(),
            "end_point": self.end_point.to_dict()
        }

class DayPlan(BaseModel):
    """Represents a day plan."""
    date: str = ""
    start_time: str = "08:00 AM"
    end_time: str = ""
    is_finished: bool = False
    travel_list: List[str] = Field(default_factory=list)
    route: List[Route] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def to_dict(self):
        return {
            "start_time": self.start_time,
            "travel_list": [poi for poi in self.travel_list]
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

    def __init__(self, cluster_dict: Dict[int, List[Dict]],
    start_time: str, end_time: str, day: str):
        # start_time = "2025-04-04"

        for i in range(int(day)):
            day_id = f"day{i + 1}"
            curr_date = time.mktime(time.strptime(start_time, "%Y-%m-%d")) + i * 86400
            curr_date_str = time.strftime("%Y-%m-%d", time.localtime(curr_date))

            self.plans[day_id] = DayPlan(
                date=curr_date_str,
                travel_list=[],
                route=[]
            )

        for cluster_id, poi_list in cluster_dict.items():
            self.clusters[cluster_id] = []
            print('mtfk')
            for poi in poi_list:
                print(poi.get("location", ""))
                location = poi.get("location", "")
                poi_index = poi['poi_index']
                longitude, latitude = location.split(",") if location else (0.0, 0.0)
                curr_poi = POI(
                    id=poi["id"],
                    name=poi["name"],
                    location=location,
                    latitude=float(latitude),
                    longitude=float(longitude),
                    city_code=poi.get("city_code", ""),
                    opening_hours=poi["opentime"],
                    opentime=poi["opentime"],
                    open_time_seconds=poi.get("open_time_seconds", 0),
                    close_time_seconds=poi.get("close_time_seconds", 0),
                    rating=poi.get("rating", "4.5"),
                    duration=float(poi["duration"]) if "duration" in poi else 1.0,
                    poi_index=poi_index,
                )

                self.pois[poi_index] = curr_poi
                self.clusters[cluster_id].append(poi_index)
                self.poi_index_int += max(self.poi_index_int, int(poi_index[1: ]))

        return

    arrange_ment: dict = {}

    poi_index_int: int = 0
    restaurant_index_int: int = 0
    hotel_index_int: int = 0

    # 将 pois 转换为 markdown 的函数
    def tranform_pois_to_markdown(self):
        """Transform pois to markdown."""
        if len(self.pois) == 0:
            return "### 注意 ###\n -当前暂时未收集到景点POI信息\n\n"

        markdown = "## 景点信息如下：\n"
        for idx, (poi_id, poi) in enumerate(self.pois.items(), 1):
            markdown += f"### {poi_id}. {poi.name}\n"
            markdown += f"**开放时间：**{poi.opening_hours}\n"
            # 游玩时长
            markdown += f"**预计游玩时长：**{poi.duration}小时\n"
            markdown += "---\n"  # 添加分隔线

        return markdown

    # 将 hotels 转换为 markdown 的函数
    def tranform_hotels_to_markdown(self):
        """Transform hotels to markdown."""
        if len(self.hotels) == 0:
            return "### 注意 ###\n -当前暂时未收集到酒店POI信息\n\n"

        markdown = "## 酒店信息如下：\n"

        for idx, (hotel_id, hotel) in enumerate(self.hotels.items(), 1):
            markdown += f"### {hotel_id}. {hotel.name}\n"
            markdown += f"**开放时间：**{hotel.opening_hours}\n"
            markdown += "---\n"  # 添加分隔线
        return markdown

    # 将 restaurants 转换为 markdown 的函数
    def tranform_restaurants_to_markdown(self):
        """Transform restaurants to markdown."""
        if len(self.restaurants) == 0:
            return "### 注意 ###\n -当前暂时未收集到餐厅POI信息\n\n"

        markdown = "## 餐厅信息如下：\n"
        for idx, (restaurant_id, restaurant) in enumerate(self.restaurants.items(), 1):
            markdown += f"### {restaurant_id}. {restaurant.name}\n"
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
            markdown += f"### ** 按照地点位置聚类的所有景点为 ** C{cluster_id}.\n"
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
        for idx, (plan_id, plan) in enumerate(self.plans.items()):
            markdown += f"### 第{plan_id} 日期{plan.date}\n"
            markdown += f"**今天出发时间：**{plan.start_time}\n"
            markdown += "**依次要经过的POI点：**\n"
            for poi in plan.travel_list:
                markdown += f"- ID:{poi}\n"
            markdown += "**路线：**\n"
            for route in plan.route:
                markdown += f"- 从{route.start_point.poi_index}到{route.end_point.poi_index}\n"

            if plan.is_finished:
                markdown += "**今天的行程已完成**\n"
            else:
                markdown += "**今天的行程未完成**\n"

            markdown += "---\n"  # 添加分隔线

        return markdown


