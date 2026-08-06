"""第 14 章：与 MCP transport 解耦的安全只读工单内核。"""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any


class McpError(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class Ticket:
    id: str
    tenant_id: str
    title: str
    body: str


class FixedWindowLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit, self.window_seconds = limit, window_seconds
        self.hits: dict[str, list[float]] = {}

    def check(self, key: str, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        start = current - self.window_seconds
        recent = [value for value in self.hits.get(key, []) if value > start]
        if len(recent) >= self.limit:
            raise McpError("rate limit exceeded")
        recent.append(current)
        self.hits[key] = recent


class TicketTools:
    def __init__(self, tickets: list[Ticket], limiter: FixedWindowLimiter | None = None) -> None:
        self.tickets = tickets
        self.limiter = limiter or FixedWindowLimiter(100)
        self.audit: list[dict[str, Any]] = []

    def _authorize(self, principal: Principal, scope: str) -> None:
        if scope not in principal.scopes:
            raise McpError("forbidden")
        self.limiter.check(f"{principal.tenant_id}:{principal.user_id}")

    def read_ticket(self, principal: Principal, ticket_id: str) -> dict[str, str]:
        self._authorize(principal, "tickets:read")
        if not re.fullmatch(r"t-[a-zA-Z0-9_-]{1,32}", ticket_id):
            raise McpError("invalid ticket id")
        row = next(
            (ticket for ticket in self.tickets if ticket.tenant_id == principal.tenant_id and ticket.id == ticket_id),
            None,
        )
        self.audit.append({"operation": "read", "tenant": principal.tenant_id, "ticket_id": ticket_id})
        if row is None:
            # 不区分不存在和无权访问，避免枚举其他 tenant 的 id。
            raise McpError("ticket not found")
        return {"id": row.id, "title": row.title, "body": row.body[:4_000]}

    def search_tickets(
        self, principal: Principal, query: str, cursor: int = 0, limit: int = 20
    ) -> dict[str, object]:
        self._authorize(principal, "tickets:read")
        if not 1 <= limit <= 50 or cursor < 0 or len(query) > 200:
            raise McpError("invalid pagination or query")
        needle = query.casefold().strip()
        rows = [
            ticket
            for ticket in self.tickets
            if ticket.tenant_id == principal.tenant_id
            and needle in f"{ticket.title} {ticket.body}".casefold()
        ]
        page = rows[cursor : cursor + limit]
        next_cursor = cursor + len(page) if cursor + len(page) < len(rows) else None
        self.audit.append({"operation": "search", "tenant": principal.tenant_id, "count": len(page)})
        return {
            "items": [{"id": row.id, "title": row.title} for row in page],
            "next_cursor": next_cursor,
        }

