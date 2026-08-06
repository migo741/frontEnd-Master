"""第 03 章：Pydantic v2 Agent 事件协议与泛型 Tool。"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Annotated, Any, Awaitable, Callable, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EventBase(StrictModel):
    version: Literal[1] = 1
    run_id: UUID
    sequence: int = Field(ge=0)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at 必须包含时区")
        return value


class TextDelta(EventBase):
    type: Literal["text_delta"]
    text: str


class ToolRequested(EventBase):
    type: Literal["tool_requested"]
    call_id: str
    name: str
    arguments: dict[str, Any]


class ToolSucceeded(EventBase):
    type: Literal["tool_succeeded"]
    call_id: str
    result: dict[str, Any]


class ToolFailed(EventBase):
    type: Literal["tool_failed"]
    call_id: str
    code: str
    safe_message: str
    retryable: bool = False


class RunCompleted(EventBase):
    type: Literal["run_completed"]
    output: dict[str, Any]


class RunFailed(EventBase):
    type: Literal["run_failed"]
    code: str
    safe_message: str


Event = Annotated[
    TextDelta | ToolRequested | ToolSucceeded | ToolFailed | RunCompleted | RunFailed,
    Field(discriminator="type"),
]
EVENT_ADAPTER = TypeAdapter(Event)


class RunContext(StrictModel):
    tenant_id: str
    user_id: str
    scopes: frozenset[str]


ArgsT = TypeVar("ArgsT", bound=BaseModel)
ResultT = TypeVar("ResultT", bound=BaseModel)


class Tool(Generic[ArgsT, ResultT]):
    def __init__(
        self,
        *,
        name: str,
        args_model: type[ArgsT],
        result_model: type[ResultT],
        handler: Callable[[ArgsT, RunContext], ResultT | Awaitable[ResultT]],
    ) -> None:
        self.name = name
        self.args_model = args_model
        self.result_model = result_model
        self.handler = handler

    def input_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()

    async def execute(self, raw: dict[str, Any], context: RunContext) -> ResultT:
        args = self.args_model.model_validate(raw, strict=True)
        result = self.handler(args, context)
        if inspect.isawaitable(result):
            result = await result
        return self.result_model.model_validate(result, strict=True)


class SearchArgs(StrictModel):
    query: str = Field(min_length=1, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(StrictModel):
    ids: list[str]

