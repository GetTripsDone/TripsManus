import os
import sys
from pydantic import Field
import json
from app.agent import ToolCallAgent
from app.config import config
from app.prompt.recommend_agent import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.arrange_days import ArrangeDays
from app.tool.recommend_poi import RecommendPOI
from app.schema import ToolCall
from app.logger import logger

class RecommendAgent(ToolCallAgent):
    """
    工具包含 推荐景点、合理规划每日行程安排
    """

    name: str = "RecommendAgent"
    description: str = (
        "一个可以推荐景点、安排行程的agent"
    )

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    pois: list = []  # 推荐的poi list : [[名字，时间，注意], [], .....]
    days_dict: dict = {}  # 每日安排 {day1: {poi: [poi1, poi2, ...], route: [r1, r2,...]}, day2: {poi: [], route: []}, ...}
    max_steps: int = 7

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            RecommendPOI(), ArrangeDays(), Terminate()
        )
    )

async def main():
    # Configure and run the agent
    agent = RecommendAgent(available_tools=ToolCollection(RecommendPOI(), ArrangeDays(), Terminate()))
    result = await agent.run("推荐新西兰著名景点")
    print(result)

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

