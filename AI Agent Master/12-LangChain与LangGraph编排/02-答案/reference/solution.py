"""第 12 章：框架无关的显式邮件状态图，用于确定性离线测试。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class EmailState:
    run_id: str
    email: str
    intent: str | None = None
    evidence: list[str] = field(default_factory=list)
    draft: str | None = None
    proposal: dict | None = None
    approval: Literal["pending", "approved", "rejected"] | None = None
    sent: bool = False
    node: str = "classify"
    version: int = 0


class Checkpointer:
    def __init__(self) -> None:
        self.snapshots: dict[str, list[EmailState]] = {}

    def save(self, state: EmailState) -> None:
        copy = EmailState(**{**state.__dict__, "evidence": list(state.evidence), "proposal": dict(state.proposal) if state.proposal else None})
        self.snapshots.setdefault(state.run_id, []).append(copy)


class EmailGraph:
    def __init__(self, checkpointer: Checkpointer) -> None:
        self.checkpointer = checkpointer
        self.operations: set[str] = set()

    def step(self, state: EmailState) -> EmailState:
        if state.node == "classify":
            state.intent = "refund" if "退款" in state.email else "question"
            state.node = "retrieve"
        elif state.node == "retrieve":
            state.evidence = ["policy:refund-v1"] if state.intent == "refund" else ["faq:general"]
            state.node = "draft"
        elif state.node == "draft":
            state.draft = f"根据 {state.evidence[0]} 回复"
            if state.intent == "refund":
                state.proposal = {"action": "refund_review", "email": state.email}
                state.approval = "pending"
                state.node = "await_approval"
            else:
                state.node = "send"
        elif state.node == "await_approval":
            if state.approval == "pending":
                return state
            state.node = "send" if state.approval == "approved" else "done"
        elif state.node == "send":
            operation_id = f"{state.run_id}:send"
            if operation_id not in self.operations:
                self.operations.add(operation_id)
                state.sent = True
            state.node = "done"
        state.version += 1
        self.checkpointer.save(state)
        return state

    def run_until_pause(self, state: EmailState) -> EmailState:
        while state.node != "done":
            previous = state.node
            self.step(state)
            if state.node == "await_approval" and state.approval == "pending":
                break
            if state.node == previous:
                break
        return state

