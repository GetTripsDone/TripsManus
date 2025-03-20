import aiohttp
from typing import Dict, Optional

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
                "description": "(required) 起点所在城市的adcode",
            },
            "city2": {
                "type": "string",
                "description": "(required) 终点所在城市的adcode",
            },
            "key": {
                "type": "string",
                "description": "(required) 高德地图API密钥",
            },
        },
        "required": ["origin", "destination", "city1", "city2", "key"],
    }

    async def execute(
        self,
        origin: str,
        destination: str,
        city1: str,
        city2: str,
        key: str,
    ) -> Dict[str, str]:
        """执行路线搜索，返回搜索结果。

        Args:
            origin (str): 起点坐标
            destination (str): 终点坐标
            city1 (str): 起点城市adcode
            city2 (str): 终点城市adcode
            key (str): 高德地图API密钥

        Returns:
            Dict[str, str]: 包含路线信息的字典，包括路线详情和状态信息
        """
        url = "https://restapi.amap.com/v5/direction/transit/integrated"
        params = {
            "origin": origin,
            "destination": destination,
            "city1": city1,
            "city2": city2,
            "key": key,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    if result.get("status") == "1":
                        return result
                    else:
                        return {"error": f"路线规划失败: {result.get('info')}"}
        except Exception as e:
            return {"error": f"请求失败: {str(e)}"}