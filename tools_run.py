from utils import *


def arrange(poi_list, day, my_data):
    """
    计算景点的初始游玩顺序，根据位置和游玩时间生成每日行程。
    """
    optimized_pois = optimize_daily_route(poi_list)  # selected_pois只是按照分数选择出满足游玩时间的poi，但是没有按照order
    my_data.arrange_ment[day] = optimized_pois
    return optimized_pois


def adjust(adjustment_type, new_poi_list):
    """
    根据用户偏好或常识，调整景点顺序。
    """
    pass


def search_for_poi(poi_list):
    """
    搜索景点附近的酒店或餐厅。
    """
    pass


def search_for_navi(poi_list):
    """
    为已安排的景点提供最佳路径和交通方式，并计算路程所需时间。
    """
    pass


def final_answer(poi_list, day):
    """
    整合所有信息，生成详细的旅行计划。
    """
    pass
