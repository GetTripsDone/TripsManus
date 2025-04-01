"""
This module contains function definitions for the travel planning assistant.
"""

functions = [
    {
        "name": "arrange",
        "description": "使用OR-Tools计算POI初始顺序，根据景点位置和游玩时间生成合理的每日行程安排。",
        "parameters": {
            "type": "object",
            "properties": {
                "poi_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "location": {"type": "string"},
                            "city_code": {"type": "string"}
                        },
                        "required": ["id", "name", "location", "city_code"]
                    },
                    "description": "List of POIs to arrange"
                },
                "day": {
                    "type": "integer",
                    "description": "Number of days for arrangement"
                }
            },
            "required": ["poi_list", "day"]
        }
    },
    {
        "name": "adjust",
        "description": "根据用户偏好或常识调整POI顺序，支持删除、添加、交换或重新排序POI。",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["del", "add", "swap", "rerank"],
                    "description": "Type of adjustment"
                },
                "new_poi_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "location": {"type": "string"},
                            "city_code": {"type": "string"}
                        },
                        "required": ["id", "name", "location", "city_code"]
                    },
                    "description": "New POI list after adjustment"
                }
            },
            "required": ["type", "new_poi_list"]
        }
    },
    {
        "name": "search_for_poi",
        "description": "搜索餐厅、酒店等POI，根据关键词和城市代码返回匹配的景点信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Search keyword"
                },
                "city_code": {
                    "type": "string",
                    "description": "City code for search"
                }
            },
            "required": ["keyword", "city_code"]
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
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "location": {"type": "string"},
                            "city_code": {"type": "string"}
                        },
                        "required": ["id", "name", "location", "city_code"]
                    },
                    "description": "List of POIs for navigation"
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
