import os
import sys
import json
from app.llm import LLM
from app.logger import logger
from app.schema import Message
from function_definitions import functions

llm_model = LLM(config_name="tool_call_llm")

async def think_func(sys_msg, msgs):
    should_act = False
    tool_calls = []

    json_dict = msgs.to_dict_list()

    final_functions = []
    for item in functions:
        new_format = {
            "type": "function",
            "function": item,
        }

        final_functions.append(new_format)

    logger.info(f"tool call messages is {json.dumps(json_dict, ensure_ascii=False)} tools {json.dumps(final_functions, ensure_ascii=False)}")

    response = await llm_model.ask_tool(
        messages=msgs.messages,
        system_msgs=[sys_msg],
        tools=final_functions,
    )

    logger.info(f"tool call response is {response}")

    if response and response.tool_calls:
        tool_calls = response.tool_calls
    else:
        logger.info(f"tool call response not have tool calls")

    content = response.content if response and response.content else ""

    # Log response info
    logger.info(f"cot: {content}")
    logger.info(
        f"selected {len(tool_calls) if tool_calls else 0} tools to use"
    )

    if tool_calls:
        logger.info(
            f"Tools being prepared: {[call.function.name for call in tool_calls]}"
        )

        logger.info(f"Tool arguments: {tool_calls[0].function.arguments}")

        assistant_msg = (
            Message.from_tool_calls(content=content, tool_calls=tool_calls)
            if tool_calls
            else Message.assistant_message(content)
        )

        msgs.add_message(assistant_msg)
        should_act = True

    return should_act, content, tool_calls

