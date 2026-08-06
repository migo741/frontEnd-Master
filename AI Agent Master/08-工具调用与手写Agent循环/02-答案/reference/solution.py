"""第 08 章：完全离线、可恢复、受预算控制的手写 Agent Runtime。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    final: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class Model(Protocol):
    async def next(self, events: tuple[dict[str, Any], ...]) -> ModelTurn: ...


class ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = iter(turns)

    async def next(self, events: tuple[dict[str, Any], ...]) -> ModelTurn:
        await asyncio.sleep(0)
        return next(self.turns)


@dataclass(frozen=True)
class RunContext:
    tenant_id: str
    user_id: str
    scopes: frozenset[str]


@dataclass
class Tool:
    name: str
    read_only: bool
    required_scope: str
    handler: Callable[[dict[str, Any], RunContext], dict[str, Any]]


@dataclass
class RunState:
    run_id: str
    context: RunContext
    status: Literal["running", "succeeded", "partial", "failed"] = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    turns: int = 0
    tool_calls: int = 0
    seen: dict[str, int] = field(default_factory=dict)


class Runtime:
    def __init__(self, tools: list[Tool], *, max_turns: int = 5, max_tools: int = 8, max_repeats: int = 2) -> None:
        self.tools = {tool.name: tool for tool in tools}
        self.max_turns = max_turns
        self.max_tools = max_tools
        self.max_repeats = max_repeats

    @staticmethod
    def _fingerprint(call: ToolCall) -> str:
        raw = json.dumps(call.arguments, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(f"{call.name}:{raw}".encode()).hexdigest()

    def _execute(self, call: ToolCall, state: RunState) -> dict[str, Any]:
        tool = self.tools.get(call.name)
        if tool is None:
            return {"ok": False, "code": "unknown_tool", "call_id": call.call_id}
        if tool.required_scope not in state.context.scopes:
            return {"ok": False, "code": "forbidden", "call_id": call.call_id}
        # 控制字段不能由模型提供。
        forbidden = {"tenant_id", "user_id", "approved", "scope"} & call.arguments.keys()
        if forbidden:
            return {"ok": False, "code": "control_field_injection", "call_id": call.call_id}
        try:
            data = tool.handler(dict(call.arguments), state.context)
            return {"ok": True, "data": data, "call_id": call.call_id}
        except Exception as exc:
            return {"ok": False, "code": "tool_error", "error_type": type(exc).__name__, "call_id": call.call_id}

    async def run(self, model: Model, state: RunState) -> RunState:
        while state.status == "running":
            if state.turns >= self.max_turns or state.tool_calls >= self.max_tools:
                state.status = "partial"
                state.events.append({"type": "budget_exhausted"})
                break
            turn = await model.next(tuple(state.events))
            state.turns += 1
            if turn.final is not None:
                state.events.append({"type": "final", "text": turn.final})
                state.status = "succeeded"
                break
            if not turn.tool_calls:
                state.status = "failed"
                state.events.append({"type": "protocol_error", "code": "empty_turn"})
                break
            for call in turn.tool_calls:
                fingerprint = self._fingerprint(call)
                state.seen[fingerprint] = state.seen.get(fingerprint, 0) + 1
                if state.seen[fingerprint] > self.max_repeats:
                    state.status = "partial"
                    state.events.append({"type": "loop_detected", "call_id": call.call_id})
                    return state
                state.events.append({"type": "tool_requested", "call": call})
                result = self._execute(call, state)
                state.tool_calls += 1
                state.events.append({"type": "tool_result", "result": result})
        return state


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    action: str
    canonical_args: str
    args_hash: str


def create_proposal(proposal_id: str, action: str, arguments: dict[str, Any]) -> Proposal:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    return Proposal(proposal_id, action, canonical, hashlib.sha256(canonical.encode()).hexdigest())

def execute_approved(proposal: Proposal, approved_hash: str, operations: dict[str, str]) -> str:
    if proposal.args_hash != approved_hash:
        raise PermissionError("批准内容与执行内容不一致")
    return operations.setdefault(proposal.proposal_id, f"executed:{proposal.action}")

