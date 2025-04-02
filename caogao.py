import re
import time
import requests

# 示例文本
text = """
### 2025-03-24 星期一

**上午：**
- [RESTAURANT_START] 08:00 - 09:00: 早餐 [RESTAURANT_END]
- [P1_START] 09:00 - 13:00: 故宫博物院 [P1_END]

**中午：**
- [RESTAURANT_START] 13:00 - 14:00: 午餐 [RESTAURANT_END]

**下午：**
- [P2_START] 14:00 - 16:00: 天安门广场 [P2_END]
- [P5_START] 16:30 - 18:00: 天坛公园 [P5_END]

**晚上：**
- [RESTAURANT_START] 18:00 - 19:00: 晚餐 [RESTAURANT_END]
- [HOTEL_START] 19:00: 东城区附近的酒店 [HOTEL_END]
"""

# 提取并按顺序存储信息
# extracted_info = []

# # 按顺序查找所有匹配内容
# for match in re.finditer(r'\[(RESTAURANT|HOTEL|P\d+)_START\]\s*(\d{2}:\d{2}(?:\s*-\s*\d{2}:\d{2})?):?\s*(.+?)\s*\[\1_END\]', text):
#     poi_type = match.group(1)
#     time_info = match.group(2)
#     poi_name = match.group(3)

#     poi_info = {
#         'type': poi_type.lower(),
#         'time_info': time_info,
#         'poi_name': poi_name
#     }
#     extracted_info.append(poi_info)

# # 输出结果
# print(extracted_info)

param = {'origin': '116.30096,40.008759', 'destination': '116.289861,39.998068', 'city1': '010', 'city2': '010', 'key': '8ef18770408aef7848eac18e09ec0a17', 'show_fields': 'cost'}
origin = '116.30096,40.008759'
destination = '116.289861,39.998068'
city1 = '010'
city2 = '010'
mykey = '8ef18770408aef7848eac18e09ec0a17'
show_fields = 'cost'

def execute_navi(
    origin: str,
    destination: str,
    city1: str,
    city2: str,
):
    # url = "https://restapi.amap.com/v5/direction/transit/integrated"
    url = "https://restapi.amap.com/v5/direction/driving"
    mykey = '8ef18770408aef7848eac18e09ec0a17'
    params = {
        "origin": origin,
        "destination": destination,
        "city1": city1,
        "city2": city2,
        "key": mykey,
        "show_fields": 'cost'
    }
    # print('search for navi的params: ', params)
    result = []
    try:
        response = requests.get(url, params=params)
        time.sleep(1)
        result = response.json()
        print('result: ', result)
        if result.get("status") == "1":
            duration = result['route']['transits'][0]['cost']['duration']
            distance = result['route']['transits'][0]['distance']
            return [duration, distance]
        else:
            return []
    except Exception as e:
        return []

execute_navi(origin, destination, city1, city2)

