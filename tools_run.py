from utils import *
from context_data import ContextData, DayPlan, POI, Route


def arrange(poi_list, day, my_data):
    """
    计算景点的初始游玩顺序，根据位置和游玩时间生成每日行程。
    返回markdown格式的字符串
    """
    # 根据poi_list中的id获取POI对象
    poi_objects = [get_poi_by_id(my_data, poi_id) for poi_id in poi_list]

    optimized_pois = optimize_daily_route(poi_objects)
    if day not in my_data.plans:
        my_data.plans[day] = DayPlan(start_time=str(time.time()), travel_list=[])
    my_data.plans[day].travel_list = [poi["id"] for poi in optimized_pois]

    # 转换为markdown格式
    markdown = f"### 第{day}天行程安排\n"
    markdown += "**景点顺序:**\n"
    for poi in optimized_pois:
        markdown += f"- {poi['id']}: {poi.get('name', '')}\n"
    return markdown


def adjust(new_poi_list, day, my_data):
    """
    根据用户偏好或常识，调整景点顺序。
    new_poi_list就是index的list
    返回markdown格式的字符串
    """
    if day not in my_data.plans:
        my_data.plans[day] = DayPlan(start_time=str(time.time()), travel_list=[])
    my_data.plans[day].travel_list = new_poi_list

    # 转换为markdown格式
    markdown = f"### 第{day}天调整后的行程\n"
    markdown += "**调整后的景点顺序:**\n"
    for poi_id in new_poi_list:
        poi = my_data.pois.get(poi_id) or my_data.hotels.get(poi_id) or my_data.restaurants.get(poi_id)
        if poi:
            markdown += f"- {poi_id}: {poi.name}\n"
    return markdown


def search_for_poi(keyword, city_code, poi_type, my_data):
    """
    搜索景点附近的酒店或餐厅。
    返回markdown格式的字符串
    """
    res = parse_res(execute(keyword, city_code))
    if poi_type == "hotel":
        cur_index = 'H' + str(my_data.hotel_index)
        my_data.hotel_index += 1
        res["poi_index"] = cur_index
        my_data.hotels[cur_index] = POI(
            id=res.get('id', ''),
            name=res.get('name', ''),
            opening_hours=res.get('opening_hours', ''),
            duration=res.get('duration', 0)
        )
    else:
        cur_index = 'R' + str(my_data.restaurant_index)
        my_data.restaurant_index += 1
        res["poi_index"] = cur_index
        my_data.restaurants[cur_index] = POI(
            id=res.get('id', ''),
            name=res.get('name', ''),
            opening_hours=res.get('opening_hours', ''),
            duration=res.get('duration', 0)
        )

    # 转换为markdown格式
    markdown = f"### 新增{poi_type}信息\n"
    markdown += f"**名称:** {res.get('name', '')}\n"
    markdown += f"**地址:** {res.get('address', '')}\n"
    markdown += f"**开放时间:** {res.get('opening_hours', '')}\n"
    markdown += f"**ID:** {cur_index}\n"
    return markdown


def get_poi_by_id(my_data, poi_id):
    """
    根据POI ID从对应的数据字典中获取POI对象
    """
    return (
        my_data.hotels.get(poi_id) if poi_id.startswith('H') else
        my_data.restaurants.get(poi_id) if poi_id.startswith('R') else
        my_data.pois.get(poi_id)
    )


def search_for_navi(poi_list, my_data):
    """
    为已安排的景点提供最佳路径和交通方式，并计算路程所需时间。
    获取city_code和poi_name需要根据pois的info来解析获取，因为poi_list中只有poi的index
    返回markdown格式的字符串
    """
    routes = []

    if len(poi_list) < 2:
        return "### 导航信息\n**提示:** 至少需要2个景点才能计算路线\n"

    markdown = "### 景点间导航信息\n"

    for i in range(len(poi_list) - 1):
        start_poi_id = poi_list[i]
        end_poi_id = poi_list[i+1]

        # Get POI from appropriate dictionary based on prefix
        start_poi = get_poi_by_id(my_data, start_poi_id)
        end_poi = get_poi_by_id(my_data, end_poi_id)

        if not start_poi or not end_poi:
            continue

        # Get location info from POIs
        start_location = f"{start_poi.longitude},{start_poi.latitude}"
        end_location = f"{end_poi.longitude},{end_poi.latitude}"

        # Call navigation API
        navi_result = execute_navi(
            origin=start_location,
            destination=end_location,
            city1=start_poi.city_code,
            city2=end_poi.city_code
        )

        if navi_result:
            duration, distance = navi_result
            routes.append({
                'start_point': start_poi_id,
                'end_point': end_poi_id,
                'duration': duration,
                'distance': distance
            })

            markdown += f"**从 {start_poi.name} 到 {end_poi.name}**\n"
            markdown += f"- 预计时间: {duration}分钟\n"
            markdown += f"- 距离: {distance}公里\n\n"

    # Save routes to day plan
    day = len(my_data.plans)  # Assuming current day is next in sequence

    # Convert routes to Route objects
    route_objects = []
    for route in routes:
        start_poi = get_poi_by_id(my_data, route['start_point'])
        end_poi = get_poi_by_id(my_data, route['end_point'])
        if start_poi and end_poi:
            route_objects.append(Route(start_poi, end_poi))

    # Initialize or update day plan
    if day not in my_data.plans:
        my_data.plans[day] = DayPlan(
            start_time=str(time.time()),
            travel_list=poi_list,
            route=route_objects
        )
    else:
        my_data.plans[day].route = route_objects

    return markdown


def final_answer(my_data):
    """
    整合所有信息，生成详细的旅行计划。
    返回完整的markdown格式行程计划
    """
    if not my_data.plans:
        return "### 旅行计划\n**提示:** 尚未生成任何行程信息\n"

    markdown = "# 完整旅行计划\n\n"

    # 添加景点信息
    markdown += "## 景点信息\n"
    markdown += my_data.tranform_pois_to_markdown()

    # 添加酒店信息
    markdown += "## 酒店信息\n"
    markdown += my_data.tranform_hotels_to_markdown()

    # 添加餐厅信息
    markdown += "## 餐厅信息\n"
    markdown += my_data.tranform_restaurants_to_markdown()

    # 添加每日行程
    markdown += "## 每日行程安排\n"
    for day, plan in my_data.plans.items():
        markdown += f"### 第{day}天\n"
        markdown += f"**出发时间:** {plan.start_time}\n"
        markdown += "**景点顺序:**\n"
        for poi_id in plan.travel_list:
            poi = get_poi_by_id(my_data, poi_id)
            if poi:
                markdown += f"- {poi_id}: {poi.name}\n"

        if plan.route:
            markdown += "**路线导航:**\n"
            for route in plan.route:
                markdown += f"- 从 {route.start_point.name} 到 {route.end_point.name}\n"

        markdown += "\n"

    return markdown
