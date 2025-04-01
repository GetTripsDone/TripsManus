"""
This module contains function definitions for the travel planning assistant.
"""

functions = [
    {
        "name": "arrange",
        "description": "一个计算POI游玩先后顺序的工具，根据景点位置和游玩时间生成合理的每日行程安排。",
        "parameters": {
            "type": "object",
            "properties": {
                "poi_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                        },
                        "required": []
                    },
                    "description": "POI的index列表，[P1, P2, P3,...]，index不一定连续，是从某类簇中选出的POI子集"
                },
                "day": {
                    "type": "integer",
                    "description": "第几天的安排"
                }
            },
            "required": ["poi_list", "day"]
        }
    },
    {
        "name": "adjust",
        "description": "根据用户query的偏好或常识调整arrange返回的POI顺序，支持删除、添加、交换或重新排序POI。",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["del", "add", "swap", "rerank"],
                    "description": "如何调整POI顺序，del: 删除POI，add: 添加POI，swap: 交换POI位置，rerank: 重新调整POI顺序"
                },
                "new_poi_list": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "properties": {
                        },
                        "required": []
                    },
                    "description": "重新调整后的排好序的POI index列表"
                }
            },
            "required": ["type", "new_poi_list"]
        }
    },
    {
        "name": "search_for_poi",
        "description": "一个搜索景点附近酒店、餐厅的工具，根据关键词来搜索餐厅、酒店等POI",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，例如：'颐和园附近的烤鸭店'、'天坛附近的涮肉'"
                },
                "city_code": {
                    "type": "string",
                    "description": "你要搜索的点所在城市的的城市编码"
                },
                "type": {
                    "type": "string",
                    "enum": ["hotel", "restaurant"],
                    "description": "搜索的POI类型，hotel: 酒店，restaurant: 餐厅"
                },
            },
            "required": ["keyword", "city_code", "type"]
        }
    },
    {
        "name": "search_for_navi",
        "description": "为已安排的POI搜索导航路线，提供景点之间的最佳路径和交通方式。",
        "parameters": {
            "type": "object",
            "properties": {
                "poi_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                        },
                        "required": []
                    },
                    "description": "POI和hotel、restaurant的index列表，已经被排好序，[H1, R1, P1, P2, P3, R1, ...]，"
                }
            },
            "required": ["poi_list"]
        }
    },
    {
        "name": "final_answer",
        "description": "最终确定并返回旅行计划，包含所有景点的详细行程安排和导航信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "最终的返回结果"
                }
            },
            "required": ["answer"]
        }
    }
]
