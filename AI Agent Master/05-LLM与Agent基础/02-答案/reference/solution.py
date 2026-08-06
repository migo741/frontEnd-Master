"""第 05 章：Agent 适用性决策与不可绕过的运行预算。"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Architecture(StrEnum):
    CODE = "code"
    WORKFLOW = "workflow"
    SINGLE_AGENT = "single-agent"
    MULTI_AGENT = "multi-agent"


def choose_architecture(*, steps_known: bool, dynamic_tools: bool, permission_isolation: bool, parallel_specialists: bool) -> Architecture:
    if steps_known and not dynamic_tools:
        return Architecture.CODE
    if steps_known:
        return Architecture.WORKFLOW
    if permission_isolation or parallel_specialists:
        return Architecture.MULTI_AGENT
    return Architecture.SINGLE_AGENT


@dataclass(frozen=True)
class BudgetLimits:
    max_turns: int
    max_tool_calls: int
    max_tokens: int
    max_cost_usd: float
    deadline: float
    max_repeats: int = 2
    max_no_progress: int = 2


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class RunBudget:
    limits: BudgetLimits
    turns: int = 0
    tool_calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    no_progress: int = 0
    _action_counts: dict[str, int] = field(default_factory=dict)

    def _check_deadline(self) -> None:
        if time.monotonic() >= self.limits.deadline:
            raise BudgetExceeded("deadline")

    def reserve_model(self, estimated_tokens: int) -> None:
        self._check_deadline()
        if self.turns + 1 > self.limits.max_turns:
            raise BudgetExceeded("turns")
        if self.tokens + estimated_tokens > self.limits.max_tokens:
            raise BudgetExceeded("tokens")
        self.turns += 1
        self.tokens += estimated_tokens

    def settle_model(self, *, actual_tokens: int, cost_usd: float) -> None:
        self.tokens = max(0, self.tokens + actual_tokens)
        self.cost_usd += cost_usd
        if self.cost_usd > self.limits.max_cost_usd:
            raise BudgetExceeded("cost")

    def reserve_tool(self, name: str, arguments: dict[str, Any]) -> None:
        self._check_deadline()
        if self.tool_calls + 1 > self.limits.max_tool_calls:
            raise BudgetExceeded("tool_calls")
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        fingerprint = hashlib.sha256(f"{name}:{canonical}".encode()).hexdigest()
        count = self._action_counts.get(fingerprint, 0) + 1
        self._action_counts[fingerprint] = count
        if count > self.limits.max_repeats:
            raise BudgetExceeded("repeated_action")
        self.tool_calls += 1

    def record_progress(self, previous_version: int, current_version: int) -> None:
        self.no_progress = 0 if current_version > previous_version else self.no_progress + 1
        if self.no_progress > self.limits.max_no_progress:
            raise BudgetExceeded("no_progress")


@dataclass(frozen=True)
class RunTerminal:
    status: Literal["succeeded", "partial", "awaiting_approval", "cancelled", "failed"]
    completed: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    safe_message: str = ""

