"""真实 FastMCP stdio Server；认证信息必须由受信 transport 注入。"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from solution import Principal, Ticket, TicketTools


mcp = FastMCP("tenant-ticket-reader")
service = TicketTools([
    Ticket("t-100", "demo", "Login failed", "Reset MFA and retry."),
    Ticket("t-101", "demo", "Invoice", "Invoice is ready."),
])


def authenticated_principal() -> Principal:
    # stdio 仅作本地演示。远程部署必须验证网关签发的短期 token，不能信任模型参数。
    tenant = os.environ.get("MCP_DEMO_TENANT", "demo")
    user = os.environ.get("MCP_DEMO_USER", "local-user")
    return Principal(tenant, user, frozenset({"tickets:read"}))


@mcp.tool()
def read_ticket(ticket_id: str) -> dict[str, str]:
    """Read a ticket visible to the authenticated tenant."""
    return service.read_ticket(authenticated_principal(), ticket_id)


@mcp.tool()
def search_tickets(query: str, cursor: int = 0, limit: int = 20) -> dict[str, object]:
    """Search visible tickets with bounded pagination."""
    return service.search_tickets(authenticated_principal(), query, cursor, limit)


@mcp.resource("knowledge://support/{article}")
def support_article(article: str) -> str:
    articles = {"mfa": "Reset MFA only after identity verification."}
    if article not in articles:
        raise ValueError("article not found")
    return articles[article]


if __name__ == "__main__":
    mcp.run(transport="stdio")

