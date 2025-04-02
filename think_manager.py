import os
import sys
import json
from app.llm import LLM
from app.logger import logger
from app.schema import Message
from function_definitions import functions
import json
from prompt import next_prompt

llm_model = LLM(config_name="tool_call_llm")

async def think_func(sys_msg, msgs):
    should_act = False
    tool_calls = []

    msgs.add_message(Message.user_message(next_prompt))

    json_dict = msgs.to_dict_list()

    final_functions = []
    for item in functions:
        new_format = {
            "type": "function",
            "function": item,
        }

        final_functions.append(new_format)

    #logger.info(f"tool call messages is {json.dumps(json_dict, ensure_ascii=False)} \n\ntools {json.dumps(final_functions, ensure_ascii=False)}")

    response = await llm_model.ask_tool(
        messages=msgs.messages,
        system_msgs=[sys_msg],
        tools=final_functions,
    )

    #logger.info(f"tool call response is {response}")

    if response and response.tool_calls:
        tool_calls = response.tool_calls
    else:
        logger.info(f"tool call response not have tool calls")
        if response and response.content:
            # 判断结果最后是否包含上述json结构，包含的话，就将json内部的信息解析成 toolcall 的形式加入 curr_tool_calls
            if "```json" in response.content and "```" in response.content:
                json_str = response.content.split("```json")[1].split("```")[0]

                json_data = json.loads(json_str)
                tool_call = ToolCall(
                    id="1",
                    function= Function(
                        name=json_data["name"],
                        arguments=json.dumps(json_data["parameters"], ensure_ascii=False),
                    ),
                )

                tool_calls.append(tool_call)

    content = response.content if response and response.content else ""

    # Log response info
    logger.info(f"cot: {content}")
    logger.info(
        f"selected {len(tool_calls) if tool_calls else 0} tools to use"
    )

    if tool_calls:
        for tool_call in tool_calls:
            logger.info(
                f"Tool name: {tool_call.function.name}, arguments: {tool_call.function.arguments}"
            )

        assistant_msg = (
            Message.from_tool_calls(content=content, tool_calls=tool_calls)
            if tool_calls
            else Message.assistant_message(content)
        )

        msgs.add_message(assistant_msg)
        should_act = True

    return should_act, content, tool_calls

