import re
import aiohttp
from typing import Dict, Optional

from app.tool.base import BaseTool

'''
    res_dict = {
    poi_name: [name, location, play_time],
'''

class SearchPOI(BaseTool):
    name: str = "search_poi"
    description: str = """根据关键词和城市搜索景点位置信息。
    该工具调用高德地图API来获取景点的详细位置信息，包括经纬度坐标。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) 搜索关键词，往往是某地点的名称、别名或是口语化描述",
            },
        },
        "required": ['query'],
    }

    async def execute(
        self,
        query: str,
        pois: Optional[list] = None,  # [["天安门", "1", ""], ["雍和宫", "2", ""], ["天坛公园", "2", ""]]
    ):
        mykey = '777e65792758b03da95607d112079834'
        url = "https://restapi.amap.com/v5/place/text"
        result = []
        params = {
            "keywords": query,
            "key": mykey,
        }
        poi_play_time = 1
        if pois:
            for poi in pois:
                poi_name, poi_play_time, _ = poi[0], poi[1], poi[2]
                if poi_name == query:
                    break
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    results = await response.json()
                    result = results['pois'][0]
                    result = [result['name'], result['location'], poi_play_time, result['id'], result['citycode']]
        except:
            return []
        return result


