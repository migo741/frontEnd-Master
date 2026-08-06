"""第 06 章：供应商无关模型网关、统一事件与应用级事件回放。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Capabilities:
    structured: bool
    tools: bool
    streaming: bool


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    require_structured: bool = False
    require_tools: bool = False


@dataclass(frozen=True)
class ModelEvent:
    type: str
    data: dict[str, Any]


class ProviderError(RuntimeError):
    def __init__(self, category: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable


class Provider(Protocol):
    capabilities: Capabilities

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...


class FakeProvider:
    def __init__(self, events: list[ModelEvent | Exception], capabilities: Capabilities | None = None) -> None:
        self.events = events
        self.capabilities = capabilities or Capabilities(True, True, True)
        self.calls = 0

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        self.calls += 1
        for event in self.events:
            await asyncio.sleep(0)
            if isinstance(event, Exception):
                raise event
            yield event


class ModelGateway:
    def __init__(self, provider: Provider, *, max_attempts: int = 2) -> None:
        self.provider = provider
        self.max_attempts = max_attempts

    def _validate_capabilities(self, request: ModelRequest) -> None:
        if request.require_structured and not self.provider.capabilities.structured:
            raise ProviderError("unsupported", "structured output 不受支持", retryable=False)
        if request.require_tools and not self.provider.capabilities.tools:
            raise ProviderError("unsupported", "tools 不受支持", retryable=False)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        self._validate_capabilities(request)
        for attempt in range(1, self.max_attempts + 1):
            emitted = False
            try:
                async for event in self.provider.stream(request):
                    emitted = True
                    yield event
                return
            except ProviderError as exc:
                # 已向调用者发出任何增量后，不能无提示重放导致重复文本/工具。
                if emitted or not exc.retryable or attempt == self.max_attempts:
                    raise
                await asyncio.sleep(0)


@dataclass
class EventLog:
    _events: dict[str, list[ModelEvent]] = field(default_factory=dict)

    def append(self, run_id: str, event: ModelEvent) -> int:
        events = self._events.setdefault(run_id, [])
        events.append(event)
        return len(events)

    def replay(self, run_id: str, after: int = 0) -> list[tuple[int, ModelEvent]]:
        return list(enumerate(self._events.get(run_id, [])[after:], start=after + 1))

