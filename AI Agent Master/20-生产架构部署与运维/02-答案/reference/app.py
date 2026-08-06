"""最小 FastAPI ingress；真实任务由 durable worker 异步消费。"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from solution import TenantFairQueue


app = FastAPI(title="Enterprise Agent API", version="1.0.0")
queue = TenantFairQueue(per_tenant_limit=100)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=r"^run-[A-Za-z0-9_-]{1,64}$")
    message: str = Field(min_length=1, max_length=8_000)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/runs", status_code=status.HTTP_202_ACCEPTED)
def create_run(request: RunRequest, x_tenant_id: str = Header(min_length=1, max_length=64)) -> dict[str, str]:
    try:
        inserted = queue.enqueue(x_tenant_id, request.run_id)
    except OverflowError as exc:
        raise HTTPException(status_code=429, detail="tenant queue full") from exc
    return {"run_id": request.run_id, "status": "queued" if inserted else "already_queued"}

