import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from core.client import ContentDelta, ToolCallDelta, StreamEnd, stream_completion
from core.usage import UsageStats


@dataclass
class TextDelta:
    content: str


@dataclass
class ToolCallStart:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    id: str
    name: str
    output: str
    is_error: bool


@dataclass
class Finished:
    usage: UsageStats


class AgentLoop:
    def __init__(self, model, messages, system_prompt, tools, permission_fn, effort=None):
        self.model = model
        self.messages = messages  # by reference — caller sees appended tool calls
        self.system_prompt = system_prompt
        self.tools = tools
        self.permission_fn = permission_fn
        self.effort = effort

    async def run(self) -> AsyncGenerator[TextDelta | ToolCallStart | ToolResult | Finished, None]:
        total_usage = UsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0, elapsed_seconds=0.0)

        while True:
            content = ""
            tool_call_accum: dict[int, dict] = {}

            async for event in stream_completion(
                messages=self.messages,
                model=self.model,
                system_prompt=self.system_prompt,
                tools=self.tools.get_tool_schemas(),
                effort=self.effort,
            ):
                if isinstance(event, ContentDelta):
                    yield TextDelta(content=event.text)
                    content += event.text
                elif isinstance(event, ToolCallDelta):
                    idx = event.index
                    if idx not in tool_call_accum:
                        tool_call_accum[idx] = {"id": event.id, "name": event.name, "arguments": ""}
                    else:
                        if event.id:
                            tool_call_accum[idx]["id"] = event.id
                        if event.name:
                            tool_call_accum[idx]["name"] = event.name
                    tool_call_accum[idx]["arguments"] += event.arguments_chunk
                elif isinstance(event, StreamEnd):
                    total_usage.prompt_tokens += event.usage.prompt_tokens
                    total_usage.completion_tokens += event.usage.completion_tokens
                    total_usage.total_tokens += event.usage.total_tokens
                    total_usage.elapsed_seconds += event.usage.elapsed_seconds

            # Build assistant message
            assistant_msg: dict = {"role": "assistant"}
            if content:
                assistant_msg["content"] = content
            if tool_call_accum:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in [tool_call_accum[idx] for idx in sorted(tool_call_accum.keys())]
                ]
            self.messages.append(assistant_msg)

            # If no tool calls, we're done
            if not tool_call_accum:
                yield Finished(usage=total_usage)
                return

            # Execute tool calls
            tool_results = []
            for idx in sorted(tool_call_accum.keys()):
                tc = tool_call_accum[idx]
                try:
                    arguments = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                yield ToolCallStart(id=tc["id"], name=tc["name"], arguments=arguments)

                if self.tools.needs_permission(tc["name"]):
                    allowed = await self.permission_fn(tc["name"], arguments)
                    if not allowed:
                        result_text = "Error: User denied this tool call"
                        yield ToolResult(id=tc["id"], name=tc["name"], output=result_text, is_error=True)
                        tool_results.append({"role": "tool", "tool_call_id": tc["id"], "content": result_text})
                        continue

                result_text = await self.tools.execute(tc["name"], arguments)
                is_error = result_text.startswith("Error:")
                yield ToolResult(id=tc["id"], name=tc["name"], output=result_text, is_error=is_error)
                tool_results.append({"role": "tool", "tool_call_id": tc["id"], "content": result_text})

            self.messages.extend(tool_results)
