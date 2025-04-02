from utils import *


def arrange(poi_list, day, my_data):
    """
    计算景点的初始游玩顺序，根据位置和游玩时间生成每日行程。
    """
    optimized_pois = optimize_daily_route(poi_list)
    if day not in my_data.plans:
        my_data.plans[day] = DayPlan(start_time=str(time.time()), travel_list=[])
    my_data.plans[day].travel_list = [poi["id"] for poi in optimized_pois]
    return optimized_pois


def adjust(new_poi_list, day, my_data):
    """
    根据用户偏好或常识，调整景点顺序。
    new_poi_list就是index的list
    """
    if day not in my_data.plans:
        my_data.plans[day] = DayPlan(start_time=str(time.time()), travel_list=[])
    my_data.plans[day].travel_list = new_poi_list
    return new_poi_list


def search_for_poi(keyword, city_code, poi_type, my_data):
    """
    搜索景点附近的酒店或餐厅。
    """
    res = parse_res(execute(keyword, city_code))
    if poi_type == "hotel":
        cur_index = 'H' + str(my_data.hotel_index)
        my_data.hotel_index += 1
        res["poi_index"] = cur_index
        my_data.hotels.append(res)
    else:
        cur_index = 'R' + str(my_data.restaurant_index)
        my_data.restaurant_index += 1
        res["poi_index"] = cur_index
        my_data.restaurants.append(res)
    return res


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
    """
    routes = []

    if len(poi_list) < 2:
        return routes

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

    return routes


def final_answer():
    """
    整合所有信息，生成详细的旅行计划。
    """
    return
