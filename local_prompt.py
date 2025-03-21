import os
import sys

Daily_Plan_SysPrompt = """



"""

Daily_Plan_UserPrompt = """
当前用户的输入为:\n
"""

PROMPT_JSON = """任务背景：
你需要根据所给出的旅行地点详细信息，抽取出相应的关键信息，并整理成JSON的格式输出。

要求：
1. 输出结果必须是JSON格式的list，不要有任何其他内容
2. 你输出的list每个元素代表每个景点的信息，格式是字典，字典的字段为：景点名称、所在城市、景点介绍、预估游玩时长。整体的格式示例如下：[{"name1": "xxx", "city": "xxx", "description": "xxx", "duration": "xxx"}, {"name2": "xxx", "city": "xxx", "description": "xxx", "duration": "xxx"}, ...]
3. 预估游玩时长单位是小时，并且最小间隔是0.5。如果输入文本的预估游玩时长是范围，请取中间值
4. 你要抽取输入文本中的所有景点信息，不要有遗漏

示例case：
输入：
1.故宫博物院
 - 北京
 - 明清两代皇家宫殿建筑群，世界文化遗产
 - 预估游玩时长：3-4小时
2. 天坛公园
 - 北京
 - 明清皇帝祭天祈谷的祭坛建筑群
 - 预估游玩时长：2-3小时
3. 八达岭长城
 - 北京
 - 保存最完好的明长城精华段
 - 预估游玩时长：4-6小时

输出：
[{"name": "故宫博物院", "city": "北京", "description": "明清两代皇家宫殿建筑群，世界文化遗产", "duration": "3.5"}, {"name": "天坛公园", "city": "北京", "description": "明清皇帝祭天祈谷的祭坛建筑群", "duration": "2.5"}, {"name":"八达岭长城", "city": "北京", "description": "保存最完好的明长城精华段", "duration": "5"}]

接下来请你根据输入文本，按照上述要求和示例case，输出符合要求的JSON格式的list。
输入：
"""

mock_input_text = """# 自然风光
1. 张掖丹霞国家地质公园
   - 所在地点：张掖市临泽县和肃南县
   - 景点介绍：以其色彩斑斓的丹霞地貌著称，是摄影爱好者的天堂。
   - 预估游玩时长：3-4小时

2. 鸣沙山月牙泉
   - 所在地点：敦煌市
   - 景点介绍：沙漠与清泉共存的奇观，可以体验骑骆驼和滑沙。
   - 预估游玩时长：2-3小时

3. 麦积山石窟
   - 所在地点：天水市麦积区
   - 景点介绍：以精美的泥塑艺术闻名，是中国四大石窟之一。
   - 预估游玩时长：2-3小时

# 历史文化
1. 莫高窟
   - 所在地点：敦煌市
   - 景点介绍：世界文化遗产，拥有丰富的佛教艺术壁画和雕塑。
   - 预估游玩时长：3-4小时

2. 嘉峪关关城
   - 所在地点：嘉峪关市
   - 景点介绍：明代万里长城的西端起点，被誉为“天下第一雄关”。
   - 预估游玩时长：2-3小时

3. 拉卜楞寺
   - 所在地点：甘南藏族自治州夏河县
   - 景点介绍：藏传佛教格鲁派六大寺院之一，拥有丰富的宗教文化和建筑艺术。
   - 预估游玩时长：2-3小时

# 民俗风情
1. 郎木寺
   - 所在地点：甘南藏族自治州碌曲县
   - 景点介绍：藏传佛教寺院，周围风景优美，是体验藏族文化的好去处。
   - 预估游玩时长：2-3小时

2. 夏河桑科草原
   - 所在地点：甘南藏族自治州夏河县
   - 景点介绍：广阔的草原风光，可以体验骑马和藏族民俗活动。
   - 预估游玩时长：3-4小时

3. 临夏八坊十三巷
   - 所在地点：临夏回族自治州临夏市
   - 景点介绍：回族文化街区，充满了浓郁的民族风情和历史文化。
   - 预估游玩时长：2-3小时

# 其他推荐
1. 黄河石林
   - 所在地点：白银市景泰县
   - 景点介绍：以奇特的石林地貌和黄河风光相结合，景色壮丽。
   - 预估游玩时长：3-4小时

2. 崆峒山
   - 所在地点：平凉市崆峒区
   - 景点介绍：道教名山，风景秀丽，文化底蕴深厚。
   - 预估游玩时长：3-4小时

3. 马蹄寺
   - 所在地点：张掖市肃南裕固族自治县
   - 景点介绍：集石窟艺术、祁连山风光和裕固族风情于一体的旅游景区。
   - 预估游玩时长：2-3小时
"""


PROMPT_COMBINE = """任务背景：
请你把输入的每日行程安排simplify_plan和景点信息poi_info_list进行整合，生成一个完整的行程安排，格式为JSON。

要求：
1. 你需要把poi_info_list中每个景点的信息坐标信息location整合到simplify_plan中，确保每个景点都有对应的详细信息。
2. simplify_plan中key为每一天，value为当天所有的路线list，每个元素是每一段路线，包含start、end、Transportation
3. 你生成的json格式应为{"day1": [{"start": "xxx", "end": "xxx", "Transportation": "xxx", "location": "xxx", }, {"start": "xxx", "end": "xxx", "Transportation": "xxx", "location": "xxx",}], "day2": [{"start": "xxx", "end": "xxx", "Transportation": "xxx", "location": "xxx", }, {"start": "xxx", "end": "xxx", "Transportation": "xxx", "location": "xxx",}], ...}

"""
