import asyncio
from typing import Dict

from openai import OpenAI

from app.tool.base import BaseTool


class RecommendPOI(BaseTool):
    name: str = "recommend_poi"
    description: str = """根据指定城市和游玩天数，生成个性化的景点推荐。
    该工具会调用大模型API来生成详细的景点游览建议，包括景点名称、游玩建议和时间安排。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "(required) 需要推荐景点的城市名称",
            },
            "days": {
                "type": "integer",
                "description": "(required) 计划游玩的天数，默认为1天",
                "default": 1,
            },
        },
        "required": ["city", "days"],
    }

    async def execute(self, city: str, days: int = 3) -> Dict[str, str]:
        """
        执行景点推荐，返回推荐结果。

        Args:
            city (str): 目标城市名称
            days (int, optional): 计划游玩天数，默认为1天

        Returns:
            Dict[str, str]: 包含推荐结果的字典，包括景点列表和详细建议
        """
        prompt = self._generate_prompt()
        query = f'规划{city}的{days}天游览行程。'
        try:
            recommendation = await self._call_llm(prompt, query)
            return {"recommendation": recommendation}
        except Exception as e:
            print(f"生成景点推荐时发生错误: {e}")
            return {"error": "生成推荐失败，请稍后重试"}

    def _generate_prompt(self) -> str:
        """
        生成用于请求大模型的prompt。

        Args:
            city (str): 目标城市名称
            days (int): 计划游玩天数

        Returns:
            str: 格式化的prompt字符串
        """
        return f"""作为一个专业的旅游规划顾问，请为游客推荐合适的游玩景点。

你需要根据城市和游玩天数，确定一些值得游玩的推荐景点，并且提供这些景点的适合游玩时常(单位是小时)，以及游玩建议

你最终的返回列表是一个list取名为pois，每个元素又是长度为3的list，取名poi_info，pair[0]是景点名称，pair[1]是适合游玩的时长，pair[2]是游玩建议。

具体格式如下所示:
[["", "", ""], ["", "", ""], ...]

示例：
输入：规划北京的3天游览行程。
输出：
[["天安门", "1.5", "不要携带易燃易爆等危险物品"], ["天坛公园", "3", "可以看祈年殿"], ...]

注意：
1. 请确保输出的是一个list，每个元素是长度为3的list，并且元素的类型是str，不要输出任何其他无关内容
2. 请确保适合游玩时间的单位是小时，并且最细粒度是0.5小时
3. 请确保输出的景点名称是真实存在的，并且仅局限于游玩场所，不包含餐厅
4. 请确保你选择的景区数量符合天数

接下来请根据输入，生成你的结果"""

    async def _call_llm(self, prompt: str, query: str) -> str:
        """
        调用大模型API生成推荐内容。

        Args:
            prompt (str): 输入的prompt

        Returns:
            str: 大模型生成的推荐内容
        """
        client = OpenAI(api_key="sk-f58c13fc9b4f41a5aeeb153fb157d739", base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ],
            stream=False
        )
        return response.choices[0].message.content
