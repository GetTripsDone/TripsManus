pattern = r'\[(P\d+|Restaurant|Hotel)_(?:START|END)\]([^\[]+)'
    # pattern = r'\[(P\d+|Restaurant|Hotel)_(?:START|END|start|end)\]\s*([^\[]+?)\s*\[(P\d+|Restaurant|Hotel)_(?:START|END|start|end)\]'

    # 按顺序找出所有匹配项
import re
matches = re.finditer(pattern, daily_plan_str)
current_poi = None

for match in matches:
    marker_type = match.group(1)  # P1, P2, Restaurant, Hotel等
    print('marker_type:\n', marker_type)
    poi_name = match.group(2).strip()
    print(poi_name)
