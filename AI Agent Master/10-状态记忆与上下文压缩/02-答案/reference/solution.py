"""第 10 章：带审批、版本、TTL、冲突和删除的长期记忆。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class MemoryProposal:
    proposal_id: str
    tenant_id: str
    subject_id: str
    kind: Literal["preference", "fact", "org_policy"]
    value: str
    source: str
    ttl_seconds: int
    sensitive: bool = False


@dataclass
class Memory:
    key: tuple[str, str, str]
    value: str
    source: str
    version: int
    expires_at: float


class MemoryStore:
    def __init__(self) -> None:
        self._values: dict[tuple[str, str, str], Memory] = {}
        self._tombstones: set[tuple[str, str, str]] = set()

    def approve_and_store(self, proposal: MemoryProposal, *, actor_roles: frozenset[str], expected_version: int | None = None) -> Memory:
        if proposal.sensitive:
            raise PermissionError("敏感内容不进入长期记忆")
        if proposal.kind == "org_policy" and "org_admin" not in actor_roles:
            raise PermissionError("只有管理员能写组织政策")
        key = (proposal.tenant_id, proposal.subject_id, proposal.kind)
        current = self._values.get(key)
        actual_version = current.version if current else 0
        if expected_version is not None and expected_version != actual_version:
            raise RuntimeError("memory version conflict")
        memory = Memory(key, proposal.value, proposal.source, actual_version + 1, time.time() + proposal.ttl_seconds)
        self._values[key] = memory
        self._tombstones.discard(key)
        return memory

    def get(self, tenant_id: str, subject_id: str, kind: str) -> Memory | None:
        key = (tenant_id, subject_id, kind)
        value = self._values.get(key)
        if value is None or value.expires_at <= time.time():
            return None
        return Memory(**value.__dict__)

    def delete(self, tenant_id: str, subject_id: str, kind: str) -> None:
        key = (tenant_id, subject_id, kind)
        self._values.pop(key, None)
        self._tombstones.add(key)

    def tombstoned(self, key: tuple[str, str, str]) -> bool:
        return key in self._tombstones


@dataclass(frozen=True)
class Fact:
    name: str
    value: str
    source_id: str
    priority: int


@dataclass(frozen=True)
class WorkingContext:
    facts: tuple[Fact, ...]
    recent_messages: tuple[str, ...]
    omitted_message_count: int


def compress_context(facts: list[Fact], messages: list[str], *, max_messages: int) -> WorkingContext:
    if max_messages < 0:
        raise ValueError("max_messages")
    # 同名事实选择优先级最高；来源保留以便高风险动作回源。
    ledger: dict[str, Fact] = {}
    for fact in facts:
        if fact.name not in ledger or fact.priority > ledger[fact.name].priority:
            ledger[fact.name] = fact
    recent = messages[-max_messages:] if max_messages else []
    return WorkingContext(
        tuple(sorted(ledger.values(), key=lambda f: f.name)),
        tuple(recent),
        max(0, len(messages) - len(recent)),
    )

