import asyncio
from typing import Dict

from openai import OpenAI

from app.tool.base import BaseTool


class ArrangeDays(BaseTool):
    name: str = "arrange_days"
    description: str = """根据景点位置信息和游玩时间，合理安排每日游览行程。
    该工具会调用大模型API来生成合理的每日行程安排，确保每天的行程在地理位置和时间上都是合理的。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "poi_info": {
                "type": "array",
                "description": "(required) 包含每个景点的信息，整体是一个list，每个元素也是一个list，格式为[[景点名称, 位置坐标, 推荐游玩时常, 景点id, 景点所在城市编码], [], ......]列表",
            },
            "days": {
                "type": "integer",
                "description": "(required) 计划游玩的总天数",
                "minimum": 1,
            },
        },
        "required": ["poi_info", "days"],
    }

    async def execute(self, poi_info: Dict, days: int) -> Dict[str, list]:
        """
        执行每日行程安排，返回安排结果。

        Args:
            poi_info (list): 包含景点信息的字典
            days (int): 计划游玩的总天数

        Returns:
            Dict[str, list]: 包含每日行程安排的字典，key为dayX格式
        """
        prompt = self._generate_prompt()
        try:
            arrangement = await self._call_llm(prompt, {"poi_info": poi_info, "days": days})
            return arrangement
        except Exception as e:
            print(f"生成行程安排时发生错误: {e}")
            return {"error": "生成行程安排失败，请稍后重试"}

#     def _generate_prompt(self) -> str:
#         """
#         生成用于请求大模型的prompt。

#         Returns:
#             str: 格式化的prompt字符串
#         """
#         return """作为一个专业的旅游行程规划师，请根据提供的景点信息合理安排每日行程。

# 输入信息包含：
# 1. poi_info：一个字典，其中key是景点名称，value是一个列表，包含[景点名称、位置坐标、游玩时间、游玩建议]
# 2. days：总的游玩天数

# 请你根据以下原则进行规划：
# 1. 考虑景点的地理位置（坐标），将地理位置相近的景点安排在同一天
# 2. 考虑每个景点的游玩时间，确保每天的总游玩时间合理（建议控制在4-8小时之间）
# 3. 确保所有景点都被安排，且总天数符合要求

# 你需要返回一个字典，格式如下：
# {
#     "day1": [[景点名称1, 位置1, 游玩时间1, 游玩建议1], [景点名称2, 位置2, 游玩时间2, 游玩建议2]],
#     "day2": [[景点名称3, 位置3, 游玩时间3, 游玩建议3], ...],
#     ...
# }

# 注意事项：
# 1. 返回的字典必须是合法的JSON格式
# 2. 每天的景点数量要合理，不要过多或过少
# 3. 同一天的景点尽量在地理位置上相近，减少游客在路上花费的时间
# 4. 确保每个景点的信息完整，包含名称、位置、时间和建议

# 请根据以上要求，生成合理的行程安排。"""

    def _generate_prompt(self) -> str:
        """
        生成用于请求大模型的prompt。

        Returns:
            str: 格式化的prompt字符串
        """
        return """作为一个专业的旅游行程规划师，请根据提供的景点信息合理安排每日行程。

任务说明：
1. 需要你根据输入信息生成每天的行程规划，即每天的路线，每条路线包括起点和终点，路线用r表示

输入信息是一个字典，key分别是poi_info和days：
1. poi_info：一个list，每个元素也是一个list，格式为[[景点名称, 位置坐标, 推荐游玩时常, 景点id, 景点所在城市编码], [], ......]
2. days：总的游玩天数

请你根据以下原则进行规划：
1. 考虑景点的地理位置（位置坐标），将地理位置相近的景点安排在同一天
2. 考虑每个景点的游玩时间，确保每天的总游玩时间合理（建议控制在4-8小时之间）
3. 确保所有景点都被安排，且总天数符合要求
4. 确保

你需要返回一个字典，
1. key必须为day1-dayn，其中n是总天数
2. 每个key对应的value是每天的路线，也是一个字典，value里的key为r1-rn，其中n是当天的路线数量，r对应的value是一个list，包含起点和终点的相关信息
示例格式如下：
{
    "day1": {"r1": [[起点景点名称1, 位置坐标1, 推荐游玩时常1, 景点id1, 景点所在城市编码1], [终点景点名称2, 位置坐标2, 推荐游玩时常2, 景点id2, 景点所在城市编码2]], "r2": [[], []], ...},
    "day2": {"r1": [[起点景点名称3, 位置坐标3, 推荐游玩时常3, 景点id3, 景点所在城市编码3], [起点景点名称4, 位置坐标4, 推荐游玩时常4, 景点id4, 景点所在城市编码4]], "r2": [[], []], ...},
    ...
}

注意事项：
1. 返回的字典必须是合法的JSON格式，不要有任何其他无关元素
2. 每天的景点数量要合理，不要过多或过少
3. 同一天的景点尽量在地理位置上相近，减少游客在路上花费的时间
4. 确保每个景点的信息完整，包含名称、坐标位置、推荐游玩时长、景点id、和景点所在城市编码，且这些信息要和输入的poi_info中的一一对应。

请遵循以上要求，根据输入信息生成合理的行程安排。"""

    async def _call_llm(self, prompt: str, data: Dict) -> Dict[str, list]:
        """
        调用大模型API生成行程安排。

        Args:
            prompt (str): 输入的prompt
            data (Dict): 包含景点信息和天数的字典

        Returns:
            Dict[str, list]: 包含每日行程安排的字典
        """
        client = OpenAI(api_key="sk-f58c13fc9b4f41a5aeeb153fb157d739", base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": str(data)},
            ],
            stream=False
        )
        return eval(response.choices[0].message.content)
