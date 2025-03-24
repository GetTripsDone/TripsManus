import re

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
extracted_info = []

# 按顺序查找所有匹配内容
for match in re.finditer(r'\[(RESTAURANT|HOTEL|P\d+)_START\]\s*(\d{2}:\d{2}(?:\s*-\s*\d{2}:\d{2})?):?\s*(.+?)\s*\[\1_END\]', text):
    poi_type = match.group(1)
    time_info = match.group(2)
    poi_name = match.group(3)

    poi_info = {
        'type': poi_type.lower(),
        'time_info': time_info,
        'poi_name': poi_name
    }
    extracted_info.append(poi_info)

# 输出结果
print(extracted_info)
