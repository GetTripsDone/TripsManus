import aiohttp
from typing import Dict, Optional

from app.tool.base import BaseTool


class SearchPOI(BaseTool):
    name: str = "search_poi"
    description: str = """根据关键词和城市搜索景点位置信息。
    该工具调用高德地图API来获取景点的详细位置信息，包括经纬度坐标。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "list": {
                "type": "string",
                "description": "(required) 搜索关键词的列表，往往是某地点的名称、别名或是口语化描述",
            },
        },
        "required": ["keywords"],
    }

    async def execute(
        self,
        inputs: dict,
    ):
        mykey = '8ef18770408aef7848eac18e09ec0a17'
        url = "https://restapi.amap.com/v5/place/text"
        res_dict = {}
        if 'pois' in inputs:
            pois = inputs['pois']
            for poi in pois:
                poi_name, poi_play_time, poi_note = poi[0], poi[1], poi[2]
                params = {
                    "keywords": poi_name,
                    "key": mykey,
                }
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, params=params) as response:
                            result = await response.json()
                            result = result['pois']
                            result = [[cur['name'], cur['location'], poi_play_time, poi_note] for cur in result]
                            res_dict[poi_name] = result
                except:
                    continue
        return res_dict


