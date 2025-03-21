import aiohttp
from typing import Dict, Optional
import time
import json
from app.tool.base import BaseTool


class SearchRoute(BaseTool):
    name: str = "search_route"
    description: str = """搜索两个地点之间的公交路线。
    该工具调用高德地图API来获取两点之间的公交路线信息，包括距离、时间和具体路段信息。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "(required) 起点坐标，格式：longitude,latitude",
            },
            "destination": {
                "type": "string",
                "description": "(required) 终点坐标，格式：longitude,latitude",
            },
            "city1": {
                "type": "string",
                "description": "(optional) 起点所在城市的adcode",
            },
            "city2": {
                "type": "string",
                "description": "(optional) 终点所在城市的adcode",
            }
        },
        "required": ["origin", "destination"],
    }

    async def execute(
        self,
        origin: str,
        destination: str,
        city1: str,
        city2: str,
        days: dict,
    ):
        """执行路线搜索，返回搜索结果。

        Args:
            origin (str): 起点坐标
            destination (str): 终点坐标
            city1 (str): 起点城市的citycode
            city2 (str): 终点城市的citycode
            key (str): 高德地图API密钥

        Returns:
            Dict[str, str]: 包含路线信息的字典，包括路线详情和状态信息
        """
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

        time.sleep(1)

        # r1: [["天安门", "116.397455,39.909187", "1", "B000A60DA1", "010"], ["雍和宫", "116.417296,39.947239", "2", "B000A7BGMG", "010"]]
        result = []
        day = 'day1'
        r = 'r1'
        for day, value in days.items():
            for r, cur in value.items():
                if cur[0][1] == origin and cur[1][1] == destination:
                    break
        # try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                result = await response.json()
                # if result.get("status") == "1":
                #     duration = result['route']['transits'][0]['cost']['duration']
                #     distance = result['route']['transits'][0]['cost']['distance']
                #     return [duration, distance, day, r]
                # else:
                #     return []
                duration = result['route']['transits'][0]['cost']['duration']
                distance = result['route']['transits'][0]['distance']
                return [duration, distance, day, r]
        # except Exception as e:
        #     return []
