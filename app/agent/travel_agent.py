from pydantic import Field
import json
from app.agent import ToolCallAgent
from app.config import config
from app.prompt.travel_agent import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.arrange_days import ArrangeDays
from app.tool.recommend_poi import RecommendPOI
from app.tool.search_poi import SearchPOI
from app.tool.search_route import SearchRoute
from app.schema import ToolCall
from app.logger import logger


class Travel(ToolCallAgent):
    """
    工具包含 推荐景点、搜点位置、算路、合理规划每日行程安排
    """

    name: str = "Manus"
    description: str = (
        "一个可以推荐景点、搜点、算路的行程规划agent"
    )

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    pois: list = []  # 推荐的poi list : [[名字，时间，注意], [], .....]
    days_dict: dict = {}  # 每日安排 {day1: {poi: [poi1, poi2, ...], route: [r1, r2,...]}, day2: {poi: [], route: []}, ...}
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            RecommendPOI(), SearchPOI(), SearchRoute(), Terminate(), ArrangeDays()
        )
    )

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # Parse arguments
            args = json.loads(command.function.arguments or "{}")

            # Add pois and days_dict to args if they exist
            if hasattr(self, 'pois') and self.pois:
                args['pois'] = self.pois
            if hasattr(self, 'days_dict') and self.days_dict:
                args['days_dict'] = self.days_dict

            # Execute the tool
            logger.info(f"🔧 Activating tool: '{name}'...")
            result = await self.available_tools.execute(name=name, tool_input=args)

            if type(result) == dict:
                if 'recommendation' in result:
                    self.pois = result['recommendation']
                elif 'days_dict' in result:
                    self.days_dict = result['days_dict']
            # Handle special tools
            await self._handle_special_tool(name=name, result=result)  # 特殊工具，terminate

            # Check if result is a ToolResult with base64_image
            if hasattr(result, "base64_image") and result.base64_image:
                # Store the base64_image for later use in tool_message
                self._current_base64_image = result.base64_image

                # Format result for display
                observation = (
                    f"Observed output of cmd `{name}` executed:\n{str(result)}"
                    if result
                    else f"Cmd `{name}` completed with no output"
                )
                return observation

            # Format result for display (standard case)
            observation = (
                f"执行工具 `{name}` 观测到的结果:\n{str(result)}"
                if result
                else f"执行 `{name}` 没有返回结果"
            )

            return observation
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"
