from utils import *
from context_data import ContextData, DayPlan, POI, Route


def arrange(poi_list, day, my_data):
    """
    计算景点的初始游玩顺序，根据位置和游玩时间生成每日行程。
    返回markdown格式的字符串
    """

    # Get full POI objects from index list
    poi_objects = []
    for poi_id in poi_list:
        poi = get_poi_by_id(my_data, poi_id)
        if poi:
            poi_objects.append(poi.to_poi_dict())

    optimized_pois = optimize_daily_route(poi_objects)

    day_id = f"day{day}"

    if day_id not in my_data.plans:
        my_data.plans[day_id] = DayPlan(start_time="08:00 AM", travel_list=[], route=[])
    my_data.plans[day_id].travel_list = [poi["poi_index"] for poi in optimized_pois]

    # 转换为markdown格式

    #markdown = f"### 第{day}天行程安排\n"
    #markdown += "**景点顺序:**\n"
    #for poi in optimized_pois:
    #    markdown += f"- {poi['id']}: {poi.get('name', '')}\n"

    markdown = common_markdown(my_data)
    return markdown

def common_markdown(my_data):
    """
    整合所有信息，生成详细的旅行计划。
    返回完整的markdown格式行程计划
    """
    markdown = ""
    poi_markdown = my_data.tranform_to_markdown()
    plan_markdown = my_data.tranform_plans_to_markdown()
    #cluster_markdown = my_data.tranform_clusters_to_markdown()

    #markdown += cluster_markdown
    markdown += poi_markdown
    markdown += plan_markdown

    return markdown

def adjust(new_poi_list, day, my_data):
    """
    根据用户偏好或常识，调整景点顺序。
    new_poi_list就是index的list
    返回markdown格式的字符串
    """
    day_id = f"day{day}"

    if day_id not in my_data.plans:
        my_data.plans[day_id] = DayPlan(start_time="08:00 AM", travel_list=[], route=[])
    my_data.plans[day_id].travel_list = new_poi_list

    # 转换为markdown格式
    #markdown = f"### 第{day_id}天调整后的行程\n"
    '''
    markdown += "**调整后的景点顺序:**\n"
    for poi_id in new_poi_list:
        poi = my_data.pois.get(poi_id) or my_data.hotels.get(poi_id) or my_data.restaurants.get(poi_id)
        if poi:
            markdown += f"- {poi_id}: {poi.name}\n"
    '''

    markdown = common_markdown(my_data)
    return markdown


def search_for_poi(keyword, city_code, poi_type, my_data):
    """
    搜索景点附近的酒店或餐厅。
    返回markdown格式的字符串
    """
    res = parse_res(execute(keyword, city_code))
    if poi_type == "hotel":
        cur_index = 'H' + str(my_data.hotel_index_int)
        my_data.hotel_index_int += 1
        res["poi_index"] = cur_index
        location = res.get('location', '')
        longitude, latitude = location.split(',') if location else (0.0, 0.0)
        my_data.hotels[cur_index] = POI(
            id=res.get('id', ''),
            name=res.get('name', ''),
            location=location,
            latitude=float(latitude),
            longitude=float(longitude),
            city_code=res.get('city_code', ''),
            opening_hours=res.get('opening_hours', ''),
            opentime=res.get('opening_hours', ''),
            open_time_seconds=res.get('open_time_seconds', 0),
            close_time_seconds=res.get('close_time_seconds', 0),
            rating=res.get('rating', '4.5'),
            duration=float(res.get('duration', 1.0)),
            poi_index=cur_index
        )
    else:
        cur_index = 'R' + str(my_data.restaurant_index_int)
        my_data.restaurant_index_int += 1
        res["poi_index"] = cur_index
        location = res.get('location', '')
        longitude, latitude = location.split(',') if location else (0.0, 0.0)
        my_data.restaurants[cur_index] = POI(
            id=res.get('id', ''),
            name=res.get('name', ''),
            location=location,
            latitude=float(latitude),
            longitude=float(longitude),
            city_code=res.get('city_code', ''),
            opening_hours=res.get('opening_hours', ''),
            opentime=res.get('opening_hours', ''),
            open_time_seconds=res.get('open_time_seconds', 0),
            close_time_seconds=res.get('close_time_seconds', 0),
            rating=res.get('rating', '4.5'),
            duration=float(res.get('duration', 1.0)),
            poi_index=cur_index
        )

    '''
    # 转换为markdown格式
    markdown = f"### 新增{poi_type}信息\n"
    markdown += f"**名称:** {res.get('name', '')}\n"
    markdown += f"**地址:** {res.get('address', '')}\n"
    markdown += f"**开放时间:** {res.get('opening_hours', '')}\n"
    markdown += f"**ID:** {cur_index}\n"
    '''

    markdown = common_markdown(my_data)
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


def search_for_navi(day, poi_list, my_data):
    """
    为已安排的景点提供最佳路径和交通方式，并计算路程所需时间。
    获取city_code和poi_name需要根据pois的info来解析获取，因为poi_list中只有poi的index
    返回markdown格式的字符串
    """
    routes = []

    if len(poi_list) < 2:
        return "### 导航信息\n**提示:** 至少需要2个景点才能计算路线\n"

    markdown = "### 景点间导航信息\n"
    # print('poi_list: ', poi_list)
    for i in range(len(poi_list) - 1):
        # print(f"当前遍历到了第{i}个点")
        start_poi_id = poi_list[i]
        end_poi_id = poi_list[i+1]

        # Get POI from appropriate dictionary based on prefix
        start_poi = get_poi_by_id(my_data, start_poi_id)
        # print('start_poi: ', start_poi)
        end_poi = get_poi_by_id(my_data, end_poi_id)
        # print('end_poi: ', end_poi)

        if not start_poi or not end_poi:
            print(f"Error: Invalid POI ID in poi_list: {start_poi_id} or {end_poi_id}")
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
        print('navi_result: ', navi_result)
        if navi_result:
            duration, distance = navi_result
            # 确保duration和distance是数值类型
            duration = float(duration) if isinstance(duration, str) else duration
            distance = float(distance) if isinstance(distance, str) else distance

            routes.append({
                'start_point': start_poi_id,
                'end_point': end_poi_id,
                'duration': duration,
                'distance': distance
            })

            markdown += f"**从 {start_poi.name} 到 {end_poi.name}**\n"
            markdown += f"- 预计时间: {duration/60:.1f}分钟\n"
            markdown += f"- 距离: {distance/1000:.1f}公里\n\n"

    # Save routes to day plan
    if not day:
        day = len(my_data.plans)  # Assuming current day is next in sequence

    # Convert routes to Route objects
    route_objects = []
    for route in routes:
        start_poi = get_poi_by_id(my_data, route['start_point'])
        end_poi = get_poi_by_id(my_data, route['end_point'])
        if start_poi and end_poi:
            route_objects.append(Route(start_point=start_poi, end_point=end_poi))

    day_id = f"day{day}"
    # Initialize or update day plan
    if day_id not in my_data.plans:
        my_data.plans[day_id] = DayPlan(
            travel_list=poi_list,
            route=route_objects
        )
    else:
        my_data.plans[day_id].route = route_objects
        my_data.plans[day_id].is_finished = True

    markdown = common_markdown(my_data)
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
