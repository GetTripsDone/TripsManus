# tool/planning.py
from typing import Dict, List, Literal, Optional, Tuple

from app.exceptions import ToolError
from app.tool.base import BaseTool, ToolResult
from app.logger import logger
import json

_PLANNING_TOOL_DESCRIPTION = """规划工具，允许智能体创建和管理解决复杂任务的计划。
该工具提供创建计划、更新计划步骤和跟踪进度的功能。"""


class PlanningTool(BaseTool):
    """
    A planning tool that allows the agent to create and manage plans for solving complex tasks.
    The tool provides functionality for creating plans, updating plan steps, and tracking progress.
    """

    name: str = "planning"
    description: str = _PLANNING_TOOL_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "要执行的命令。可用命令：create、update、list、get、set_active、mark_step、delete",
                "enum": [
                    "create",
                    "update",
                    "list",
                    "get",
                    "set_active",
                    "mark_step",
                    "delete",
                ],
                "type": "string",
            },
            "plan_id": {
                "description": "规划的唯一标识符。对于 create、update、set_active 、get、mark_step和 delete 命令是必需的",
                "type": "string",
            },
            "title": {
                "description": "规划的标题。对于 create、update、set_active、get、mark_step和 delete 命令是必需的",
                "type": "string",
            },
            "steps": {
                "description": "规划的步骤列表。对于 create 命令是必需的，对于 update 命令是可选的",
                "type": "array",
                "items": {"type": "string"},
            },
            "step_index": {
                "description": "要更新的步骤的索引（从 0 开始）。mark_step 命令必需",
                "type": "integer",
            },
            "step_status": {
                "description": "设置步骤的状态。与 mark_step 命令一起使用",
                "enum": ["not_started", "in_progress", "completed", "blocked", "failed"],
                "type": "string",
            },
            "step_notes": {
                "description": "步骤的附加注释。对于 mark_step 命令是可选的",
                "type": "string",
            },
            "step_result": {
                "description": "步骤执行之后的结果。与 mark_step 命令一起使用",
                "type": "string",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    plans: dict = {}  # Dictionary to store plans by plan_id
    _current_plan_id: Optional[str] = None  # Track the current active plan

    async def execute(
        self,
        *,
        command: Literal[
            "create", "update", "list", "get", "set_active", "mark_step", "delete"
        ],
        plan_id: Optional[str] = None,
        title: Optional[str] = None,
        steps: Optional[List[str]] = None,
        step_index: Optional[int] = None,
        step_status: Optional[
            Literal["not_started", "in_progress", "completed", "blocked"]
        ] = None,
        step_notes: Optional[str] = None,
        **kwargs,
    ):
        """
        Execute the planning tool with the given command and parameters.

        Parameters:
        - command: The operation to perform
        - plan_id: Unique identifier for the plan
        - title: Title for the plan (used with create command)
        - steps: List of steps for the plan (used with create command)
        - step_index: Index of the step to update (used with mark_step command)
        - step_status: Status to set for a step (used with mark_step command)
        - step_notes: Additional notes for a step (used with mark_step command)
        """

        if command == "create":
            return self._create_plan(plan_id, title, steps)
        elif command == "update":
            return self._update_plan(plan_id, title, steps)
        elif command == "list":
            return self._list_plans()
        elif command == "get":
            return self._get_plan(plan_id)
        elif command == "set_active":
            return self._set_active_plan(plan_id)
        elif command == "mark_step":
            return await self._mark_step(plan_id, step_index, step_status, step_notes)
        elif command == "delete":
            return self._delete_plan(plan_id)
        else:
            raise ToolError(
                f"Unrecognized command: {command}. Allowed commands are: create, update, list, get, set_active, mark_step, delete"
            )

    def _create_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """Create a new plan with the given ID, title, and steps."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: create")

        if plan_id in self.plans:
            raise ToolError(
                f"A plan with ID '{plan_id}' already exists. Use 'update' to modify existing plans."
            )

        if not title:
            raise ToolError("Parameter `title` is required for command: create")

        if (
            not steps
            or not isinstance(steps, list)
            or not all(isinstance(step, str) for step in steps)
        ):
            raise ToolError(
                "Parameter `steps` must be a non-empty list of strings for command: create"
            )

        # Create a new plan with initialized step statuses
        plan = {
            "plan_id": plan_id,
            "title": title,
            "steps": steps,
            "step_statuses": ["not_started"] * len(steps),
            "step_notes": [""] * len(steps),
            "step_results": [""] * len(steps),
        }

        self.plans[plan_id] = plan
        self._current_plan_id = plan_id  # Set as active plan

        return ToolResult(
            output=f"Plan created successfully with ID: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _update_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """Update an existing plan with new title or steps."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: update")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]

        if title:
            plan["title"] = title

        if steps:
            if not isinstance(steps, list) or not all(
                isinstance(step, str) for step in steps
            ):
                raise ToolError(
                    "Parameter `steps` must be a list of strings for command: update"
                )

            # Preserve existing step statuses for unchanged steps
            old_steps = plan["steps"]
            old_statuses = plan["step_statuses"]
            old_notes = plan["step_notes"]

            # Create new step statuses and notes
            new_statuses = []
            new_notes = []

            for i, step in enumerate(steps):
                # If the step exists at the same position in old steps, preserve status and notes
                if i < len(old_steps) and step == old_steps[i]:
                    new_statuses.append(old_statuses[i])
                    new_notes.append(old_notes[i])
                else:
                    new_statuses.append("not_started")
                    new_notes.append("")

            plan["steps"] = steps
            plan["step_statuses"] = new_statuses
            plan["step_notes"] = new_notes

        return ToolResult(
            output=f"Plan updated successfully: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _list_plans(self) -> ToolResult:
        """List all available plans."""
        if not self.plans:
            return ToolResult(
                output="No plans available. Create a plan with the 'create' command."
            )

        output = "Available plans:\n"
        for plan_id, plan in self.plans.items():
            current_marker = " (active)" if plan_id == self._current_plan_id else ""
            completed = sum(
                1 for status in plan["step_statuses"] if status == "completed"
            )
            total = len(plan["steps"])
            progress = f"{completed}/{total} steps completed"
            output += f"• {plan_id}{current_marker}: {plan['title']} - {progress}\n"

        return ToolResult(output=output)

    def _get_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Get details of a specific plan."""
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                raise ToolError(
                    "No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]
        return ToolResult(output=self._format_plan(plan))

    def _set_active_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Set a plan as the active plan."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: set_active")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        self._current_plan_id = plan_id
        return ToolResult(
            output=f"Plan '{plan_id}' is now the active plan.\n\n{self._format_plan(self.plans[plan_id])}"
        )

    async def _mark_step(
        self,
        plan_id: Optional[str],
        step_index: Optional[int],
        step_status: Optional[str],
        step_notes: Optional[str],
    ) -> ToolResult:
        """Mark a step with a specific status and optional notes."""
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                raise ToolError(
                    "No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        if step_index is None:
            raise ToolError("Parameter `step_index` is required for command: mark_step")

        plan = self.plans[plan_id]

        if step_index < 0 or step_index >= len(plan["steps"]):
            raise ToolError(
                f"Invalid step_index: {step_index}. Valid indices range from 0 to {len(plan['steps'])-1}."
            )

        if step_status and step_status not in [
            "not_started",
            "in_progress",
            "completed",
            "blocked",
        ]:
            raise ToolError(
                f"Invalid step_status: {step_status}. Valid statuses are: not_started, in_progress, completed, blocked"
            )

        if step_status:
            plan["step_statuses"][step_index] = step_status

        if step_status == "in_progress":
            #import asyncio
            #response, status = asyncio.run(self.run_swarm_agent(plan, step_index))

            response, status = await self.run_swarm_agent(plan, step_index)

            plan["step_statuses"][step_index] = status
            plan["step_results"][step_index] = response

        if step_notes:
            plan["step_notes"][step_index] = step_notes

        return ToolResult(
            output=f"Step {step_index} updated in plan '{plan_id}'.\n\n{self._format_plan(plan)}"
        )

    async def run_swarm_agent(self, plan: Dict, step_index: int) -> Tuple[str, str]:
        """Run the swarm agent for a specific step."""
        """
        plan = {
            "plan_id": plan_id,
            "title": title,
            "steps": steps,
            "step_statuses": ["not_started"] * len(steps),
            "step_notes": [""] * len(steps),
            "step_results": [""] * len(steps),
        }
        """
        response = "进行中"
        status = "in_progress"

        from app.agent import RecommendAgent, SearchPOINavi

        request_query = self.format_request_query(plan, step_index)
        result = ""
        logger.info(f"start swarm query: {request_query} \n当前目标: {plan["steps"][step_index]}")

        # 发送请求到 redis 缓存
        # sesson id 内存存储的
        # 数据的结构 需要去和前端的一致

        if "recommend_spots" in plan["steps"][step_index]:
            agent = RecommendAgent()
            result = await agent.run(request_query)
            response, status = self.parser_response(result)

        elif "travel_plan" in plan["steps"][step_index]:
            agent = RecommendAgent()
            result = await agent.run(request_query)
            response, status = self.parser_response(result)

        elif "search_poi" in plan["steps"][step_index]:
            agent = SearchPOINavi()
            result = await agent.run(request_query)
            response, status = self.parser_response(result)

        elif "search_route" in plan["steps"][step_index]:
            agent = SearchPOINavi()
            result = await agent.run(request_query)
            response, status = self.parser_response(result)

        logger.info(f"swarm result: {result}")

        return response, status

    def parser_response(self, result: str) -> Tuple[str, str]:
        """Parse the response from the swarm agent."""
        if result == "":
            return "失败", "failed"

        response = result
        status = "failed"

        react_vec = result.split('\n')

        for i in range(len(react_vec)):
            if "终止工具" in react_vec[i]:
                if "success" in react_vec[i]:
                    status = "completed"

        return response, status

    def format_request_query(self, plan: Dict, step_index: int) -> str:
        """Format the request query for a specific step."""

        ret = ""

        if "recommend_spots" in plan["steps"][step_index] or \
            "travel_plan" in plan["steps"][step_index]:
            for i, step in enumerate(plan["steps"]):
                if i < step_index:
                    ret += f"Step {i+1} 目的: {step}\n 结果: {plan['step_results'][i]}\n"
                elif i == step_index:
                    ret += f"Step {i+1} 目的: {step}\n"
        else:
            ret = self.parser_json_str(plan, step_index)

        return ret

    def parser_json_str(self, plan: Dict, step_index: int) -> str:
        """Parse the JSON string for a specific step."""
        ret = f"Step {step_index+1} 目的: {plan["steps"][step_index]}\n"

        if step_index == 0:
            return ret

        if "search_poi" in plan["steps"][step_index]:
            recommend_str = ""

            for i in range(step_index - 1, -1, -1):
                if "recommend_spots" in plan["steps"][i]:
                    recommend_str = plan["step_results"][i]
                    break

            if recommend_str == "":
                return ret

            recommend_vec = recommend_str.split('\n')
            for i in range(len(recommend_vec)):
                if "执行工具 `recommend_poi` 观测到的结果" in recommend_vec[i]:
                    ret = json.loads(recommend_vec[i].split('观测到的结果:')[1])["景点推荐结果"]
                    return ret
        elif "search_route" in plan["steps"][step_index]:
            day_str = ""
            for i in range(step_index - 1, -1, -1):
                if "travel_plan" in plan["steps"][i]:
                    day_str = plan["step_results"][i]
                    break

            if day_str == "":
                return ret

            day_vec = day_str.split('\n')

            for i in range(len(day_vec)):
                if "执行工具 `arrange_days` 观测到的结果" in day_vec[i]:
                    ret = json.loads(day_vec[i].split('观测到的结果:')[1])["行程安排结果"]
                    ret = json.dumps(ret, ensure_ascii=False)

                    return ret

        return ret

    def _delete_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Delete a plan."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: delete")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        del self.plans[plan_id]

        # If the deleted plan was the active plan, clear the active plan
        if self._current_plan_id == plan_id:
            self._current_plan_id = None

        return ToolResult(output=f"Plan '{plan_id}' has been deleted.")

    def _format_plan(self, plan: Dict) -> str:
        """Format a plan for display."""
        output = f"Plan: {plan['title']} (ID: {plan['plan_id']})\n"
        output += "=" * len(output) + "\n\n"

        # Calculate progress statistics
        total_steps = len(plan["steps"])
        completed = sum(1 for status in plan["step_statuses"] if status == "completed")
        in_progress = sum(
            1 for status in plan["step_statuses"] if status == "in_progress"
        )
        blocked = sum(1 for status in plan["step_statuses"] if status == "blocked")
        not_started = sum(
            1 for status in plan["step_statuses"] if status == "not_started"
        )

        output += f"Progress: {completed}/{total_steps} steps completed "
        if total_steps > 0:
            percentage = (completed / total_steps) * 100
            output += f"({percentage:.1f}%)\n"
        else:
            output += "(0%)\n"

        output += f"Status: {completed} completed, {in_progress} in progress, {blocked} blocked, {not_started} not started\n\n"
        output += "Steps:\n"

        # Add each step with its status and notes
        for i, (step, status, notes, results) in enumerate(
            zip(plan["steps"], plan["step_statuses"], plan["step_notes"], plan["step_results"])
        ):
            status_symbol = {
                "not_started": "[ ]",
                "in_progress": "[→]",
                "completed": "[✓]",
                "blocked": "[!]",
            }.get(status, "[ ]")

            output += f"{i}. {status_symbol} {step}\n"
            if notes:
                output += f"   注释: {notes}\n"
            if results:
                output += f"   返回结果: {results}\n"

        return output
