import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

from core.budget import Budget, BudgetTracker
from core.client import ContentDelta, StreamEnd, ToolCallDelta, stream_completion
from core.policy import PolicyEngine
from core.usage import UsageStats

logger = logging.getLogger("model-chat.agent")

_TRANSIENT_PATTERN = re.compile(
    r"timeout|timed out|network|connection|connect|temporary|unavailable|rate.?limit",
    re.IGNORECASE,
)


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
    stop_reason: str = "end_turn"


class _AbortedError(Exception):
    pass


class AgentLoop:
    def __init__(
        self,
        model,
        messages,
        system_prompt,
        tools,
        permission_fn,
        effort=None,
        max_iterations: int = 25,
        timeout_seconds: float = 300,
        abort_event: asyncio.Event | None = None,
        policy_engine: PolicyEngine | None = None,
        work_dir: Path | None = None,
        budget: Budget | None = None,
    ):
        self.model = model
        self.messages = messages  # by reference — caller sees appended tool calls
        self.system_prompt = system_prompt
        self.tools = tools
        self.permission_fn = permission_fn
        self.effort = effort
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.abort_event = abort_event
        self.policy_engine = policy_engine
        self.work_dir = work_dir
        self.budget_tracker = BudgetTracker(budget) if budget else None

    def _check_abort(self):
        if self.abort_event and self.abort_event.is_set():
            raise _AbortedError()

    async def run(self) -> AsyncGenerator[TextDelta | ToolCallStart | ToolResult | Finished, None]:
        total_usage = UsageStats(
            prompt_tokens=0, completion_tokens=0, total_tokens=0, elapsed_seconds=0.0
        )
        iteration = 0
        start_time = time.monotonic()

        try:
            async for event in self._loop(total_usage, iteration, start_time):
                yield event
        except _AbortedError:
            yield TextDelta(content="\n\n[Stopped: aborted by user]")
            yield Finished(usage=total_usage, stop_reason="aborted")

    async def _loop(self, total_usage, iteration, start_time):
        while True:
            self._check_abort()

            iteration += 1
            if iteration > self.max_iterations:
                yield TextDelta(
                    content=f"\n\n[Stopped: reached max iterations ({self.max_iterations})]"
                )
                yield Finished(usage=total_usage, stop_reason="max_iterations")
                return

            elapsed = time.monotonic() - start_time
            if elapsed >= self.timeout_seconds:
                yield TextDelta(content=f"\n\n[Stopped: timeout after {elapsed:.0f}s]")
                yield Finished(usage=total_usage, stop_reason="timeout")
                return

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
                    if self.budget_tracker:
                        self.budget_tracker.record(event.usage, self.model)
                        status = self.budget_tracker.check()
                        if status == "exceeded":
                            bt = self.budget_tracker
                            yield TextDelta(
                                content=f"\n\n[Stopped: budget exceeded — "
                                f"{bt.total_tokens} tokens, ${bt.estimated_cost_usd:.4f}]"
                            )
                            yield Finished(usage=total_usage, stop_reason="budget_exceeded")
                            return
                        if status == "warning":
                            bt = self.budget_tracker
                            yield TextDelta(
                                content=f"\n\n[Warning: approaching budget limit — "
                                f"{bt.total_tokens} tokens, ${bt.estimated_cost_usd:.4f}]"
                            )

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
                yield Finished(usage=total_usage, stop_reason="end_turn")
                return

            self._check_abort()

            logger.info(
                "iteration %d: %d tool call(s) — %s",
                iteration,
                len(tool_call_accum),
                ", ".join(tool_call_accum[i]["name"] for i in sorted(tool_call_accum)),
            )

            # Phase 1: parse arguments and check permissions sequentially
            sorted_indices = sorted(tool_call_accum.keys())
            parsed_calls: list[tuple[dict, dict]] = []  # (tc, arguments)
            early_results: dict[int, tuple[str, bool]] = {}  # idx -> (text, is_error)

            for i, idx in enumerate(sorted_indices):
                self._check_abort()
                tc = tool_call_accum[idx]
                try:
                    arguments = json.loads(tc["arguments"])
                except json.JSONDecodeError as exc:
                    arguments = {}
                    err = f"{tc['name']} failed: JSONDecodeError — could not parse arguments: {exc}"
                    early_results[i] = (err, True)

                yield ToolCallStart(id=tc["id"], name=tc["name"], arguments=arguments)
                parsed_calls.append((tc, arguments))

                if i not in early_results:
                    decision = (
                        self.policy_engine.evaluate(tc["name"], arguments, self.work_dir)
                        if self.policy_engine
                        else None
                    )
                    if decision and decision.action == "allow":
                        logger.debug(
                            "policy auto-approved %s (rule: %s)", tc["name"], decision.rule_id
                        )
                    elif decision and decision.action == "deny":
                        early_results[i] = (f"Denied by policy: {decision.reason}", True)
                    elif self.tools.needs_permission(tc["name"]) or (
                        decision and decision.action == "prompt"
                    ):
                        allowed = await self.permission_fn(tc["name"], arguments)
                        if not allowed:
                            early_results[i] = ("Error: User denied this tool call", True)

            # Phase 2: execute approved tools concurrently (with one retry on transient errors)
            async def _exec(i, tc, arguments, _early=early_results):
                if i in _early:
                    return _early[i]
                result_text = await self.tools.execute(tc["name"], arguments)
                is_error = result_text.startswith("Error:")
                if is_error and _TRANSIENT_PATTERN.search(result_text):
                    logger.info("retrying %s (transient error: %s)", tc["name"], result_text[:80])
                    result_text = await self.tools.execute(tc["name"], arguments)
                    is_error = result_text.startswith("Error:")
                if is_error:
                    result_text = _structured_error(tc["name"], result_text)
                return (result_text, is_error)

            results = await asyncio.gather(
                *[_exec(i, tc, args) for i, (tc, args) in enumerate(parsed_calls)],
                return_exceptions=True,
            )

            # Phase 3: yield results and build messages in original order
            tool_results = []
            for i, (tc, _args) in enumerate(parsed_calls):
                r = results[i]
                if isinstance(r, BaseException):
                    result_text = _structured_error(tc["name"], str(r))
                    is_error = True
                else:
                    result_text, is_error = r
                logger.info("  %s → %s", tc["name"], "error" if is_error else "ok")
                yield ToolResult(
                    id=tc["id"], name=tc["name"], output=result_text, is_error=is_error
                )
                tool_results.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result_text}
                )

            self.messages.extend(tool_results)


def _structured_error(tool_name: str, raw: str) -> str:
    detail = raw.removeprefix("Error:").strip() if raw.startswith("Error:") else raw
    return f"{tool_name} failed: {detail}"
