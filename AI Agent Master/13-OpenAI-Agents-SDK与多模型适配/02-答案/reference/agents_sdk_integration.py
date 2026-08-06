"""当前 OpenAI Agents SDK Python API 的最小真实集成。

安装可选依赖后运行：
    OPENAI_API_KEY=... python agents_sdk_integration.py
可用 OPENAI_MODEL 指定组织已评测并获准使用的模型；未设置时使用 SDK 默认值。
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from agents import Agent, RunContextWrapper, Runner, function_tool
from pydantic import BaseModel, ConfigDict


class OrderAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str
    status: str
    explanation: str


class OrderService:
    async def read(self, tenant_id: str, order_id: str) -> dict[str, str]:
        rows = {("tenant-a", "o-1"): "shipped"}
        status = rows.get((tenant_id, order_id))
        if status is None:
            raise LookupError("order not found")
        return {"order_id": order_id, "status": status}


@dataclass
class AppContext:
    tenant_id: str
    user_id: str
    orders: OrderService


@function_tool
async def get_order(
    ctx: RunContextWrapper[AppContext], order_id: str
) -> dict[str, str]:
    """Read one order visible to the authenticated tenant.

    Args:
        order_id: Public order identifier. Tenant is never supplied by the model.
    """
    return await ctx.context.orders.read(ctx.context.tenant_id, order_id)


def build_agent() -> Agent[AppContext]:
    options: dict[str, object] = {}
    if model := os.getenv("OPENAI_MODEL"):
        options["model"] = model
    return Agent[AppContext](
        name="Order support",
        instructions=(
            "Answer only from tool results. Never invent an order. "
            "Tenant identity comes from trusted runtime context."
        ),
        tools=[get_order],
        output_type=OrderAnswer,
        **options,
    )


async def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_API_KEY to run the live SDK example")
    result = await Runner.run(
        build_agent(),
        "查询订单 o-1",
        context=AppContext("tenant-a", "user-7", OrderService()),
        max_turns=4,
    )
    print(result.final_output.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())

