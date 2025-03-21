from pydantic import Field
import json
from app.agent import ToolCallAgent
from app.config import config
from app.prompt.search_poi_navi import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.arrange_days import ArrangeDays
from app.tool.recommend_poi import RecommendPOI
from app.tool.search_poi import SearchPOI
from app.tool.search_route import SearchRoute
from app.schema import ToolCall
from app.logger import logger
from app.sandbox.client import SANDBOX_CLIENT
from app.schema import ROLE_TYPE, AgentState, Memory, Message
from typing import List, Optional
<<<<<<< HEAD

=======
>>>>>>> 4c54dc39c8a23b9cc4fe393dcdfaae0a797dba36

class SearchPOINavi(ToolCallAgent):
    """
    只包含搜点和算路工具
    输出：
    交互完成，最终的状态是: success

已搜索到的地点、坐标和id:[["天安门", "116.397455,39.909187", "1", "B000A60DA1"], ["雍和宫", "116.417296,39.947239", "2", "B000A7BGMG"], ["天坛公园", "116.410829,39.881913", "2", "B000A81CB2"]]
    """

    name: str = "search_poi_navi"
    description: str = (
        "一个可以搜点、算路的行程规划agent"
    )
    pois: list = []
    days: list = []
    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            SearchPOI(), SearchRoute(), Terminate()
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
            if name == 'search_poi':
                args['pois'] = json.loads(self.request)
            elif name == 'search_route':
                args['days'] = json.loads(self.request)

            # Execute the tool
            logger.info(f"🔧 Activating tool: '{name}'...")
            result = await self.available_tools.execute(name=name, tool_input=args)
            if name == 'search_poi' and result:
                self.pois.append(result)
            if name == 'search_route' and result:
                self.days.append(result)  # [duration, distance, day, r]
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

            pois_res = json.dumps(self.pois, ensure_ascii=False)
            days_res = json.dumps(self.days, ensure_ascii=False)

            suffix = ''
            if name == '终止工具':
                suffix = f"搜索POI结果:{pois_res}\n路线结果:{days_res}\n执行工具 `{name}` 观测到的结果:{result}"
                self.pois = []
                self.days = []
                return suffix

            observation = (
                f"执行工具 `{name}` 观测到的结果:\n{str(result)}" + suffix
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

    async def run(self, request: Optional[str] = None) -> str:
        """Execute the agent's main loop asynchronously.

        Args:
            request: Optional initial user request to process.

        Returns:
            A string summarizing the execution results.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        self.request = request
        if request:
            self.update_memory("user", request)

        results: List[str] = []
        async with self.state_context(AgentState.RUNNING):
            while (
                self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                step_result = await self.step()

                # Check for stuck state
                if self.is_stuck():
                    self.handle_stuck_state()

                results.append(f"Step {self.current_step}: {step_result}")

            if self.current_step >= self.max_steps:
                self.current_step = 0
                self.state = AgentState.IDLE
                results.append(f"Terminated: Reached max steps ({self.max_steps})")
        await SANDBOX_CLIENT.cleanup()
<<<<<<< HEAD
        return results[-1] if results else "No steps executed"
=======
        return results[-1] if results and len(results) > 0 else "No steps executed"
>>>>>>> 4c54dc39c8a23b9cc4fe393dcdfaae0a797dba36
