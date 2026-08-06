"""第 09 章：多租户工单工具、审批幂等执行与安全语义查询。"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class RunContext:
    tenant_id: str
    user_id: str
    roles: frozenset[str]


@dataclass
class Ticket:
    ticket_id: str
    tenant_id: str
    title: str
    status: str = "open"
    comments: list[str] = field(default_factory=list)
    version: int = 1


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    tenant_id: str
    actor_id: str
    action: Literal["comment", "change_status"]
    ticket_id: str
    ticket_version: int
    arguments: dict[str, Any]
    args_hash: str
    expires_at: float


class TicketService:
    def __init__(self, tickets: list[Ticket]) -> None:
        self._tickets = {ticket.ticket_id: ticket for ticket in tickets}
        self._proposals: dict[str, Proposal] = {}
        self._operations: dict[str, dict[str, Any]] = {}
        self.audit: list[dict[str, Any]] = []

    def get(self, ticket_id: str, context: RunContext) -> Ticket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None or ticket.tenant_id != context.tenant_id:
            # 不向攻击者区分“存在但无权”与“不存在”。
            raise KeyError("ticket not found")
        return Ticket(**{**ticket.__dict__, "comments": list(ticket.comments)})

    def search(self, query: str, context: RunContext) -> list[Ticket]:
        query = query.casefold()
        return [self.get(ticket.ticket_id, context) for ticket in self._tickets.values() if ticket.tenant_id == context.tenant_id and query in ticket.title.casefold()]

    @staticmethod
    def _hash(arguments: dict[str, Any]) -> str:
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def propose(self, proposal_id: str, action: str, ticket_id: str, arguments: dict[str, Any], context: RunContext, *, ttl: float = 300) -> Proposal:
        if action not in {"comment", "change_status"}:
            raise ValueError("unsupported action")
        if {"tenant_id", "approved", "user_id"} & arguments.keys():
            raise ValueError("模型不得传控制字段")
        ticket = self.get(ticket_id, context)
        proposal = Proposal(
            proposal_id, context.tenant_id, context.user_id, action, ticket_id,
            ticket.version, dict(arguments), self._hash(arguments), time.time() + ttl,
        )
        self._proposals[proposal_id] = proposal
        self.audit.append({"event": "proposed", "proposal_id": proposal_id, "actor": context.user_id})
        return proposal

    def execute(self, proposal_id: str, approved_hash: str, operation_id: str, context: RunContext) -> dict[str, Any]:
        if operation_id in self._operations:
            return dict(self._operations[operation_id])
        proposal = self._proposals[proposal_id]
        if proposal.tenant_id != context.tenant_id or "ticket:approve" not in context.roles:
            raise PermissionError("approval forbidden")
        if proposal.expires_at < time.time():
            raise PermissionError("approval expired")
        if proposal.args_hash != approved_hash:
            raise PermissionError("proposal was changed")
        ticket = self._tickets[proposal.ticket_id]
        if ticket.version != proposal.ticket_version:
            raise RuntimeError("ticket changed; re-approval required")
        if proposal.action == "comment":
            comment = proposal.arguments.get("comment")
            if not isinstance(comment, str) or not 1 <= len(comment) <= 500:
                raise ValueError("invalid comment")
            ticket.comments.append(comment)
        else:
            status = proposal.arguments.get("status")
            if status not in {"open", "pending", "closed"}:
                raise ValueError("invalid status")
            ticket.status = status
        ticket.version += 1
        result = {"ok": True, "ticket_id": ticket.ticket_id, "version": ticket.version}
        self._operations[operation_id] = result
        self.audit.append({"event": "executed", "proposal_id": proposal_id, "operation_id": operation_id})
        return dict(result)


@dataclass(frozen=True)
class SemanticQuery:
    dataset: Literal["tickets"]
    dimensions: tuple[str, ...]
    metric: Literal["count"]
    filters: dict[str, str]
    limit: int = 100


class SemanticCompiler:
    ALLOWED_DIMENSIONS = {"status", "created_day"}
    ALLOWED_FILTERS = {"status", "created_day"}

    def compile(self, query: SemanticQuery, context: RunContext) -> tuple[str, list[Any]]:
        if not set(query.dimensions) <= self.ALLOWED_DIMENSIONS:
            raise PermissionError("dimension not allowed")
        if not set(query.filters) <= self.ALLOWED_FILTERS:
            raise PermissionError("filter not allowed")
        if not 1 <= query.limit <= 1000:
            raise ValueError("limit out of range")
        select = ", ".join(query.dimensions) if query.dimensions else "'all' AS bucket"
        clauses = ["tenant_id = ?"]
        params: list[Any] = [context.tenant_id]
        for key, value in sorted(query.filters.items()):
            clauses.append(f"{key} = ?")
            params.append(value)
        group = f" GROUP BY {', '.join(query.dimensions)}" if query.dimensions else ""
        sql = f"SELECT {select}, COUNT(*) AS count FROM tickets WHERE {' AND '.join(clauses)}{group} LIMIT ?"
        params.append(query.limit)
        return sql, params

