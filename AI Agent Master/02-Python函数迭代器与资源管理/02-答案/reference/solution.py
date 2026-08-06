"""第 02 章：保留签名的工具注册器和可关闭 NDJSON 流。"""

from __future__ import annotations

import inspect
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterator


@dataclass(frozen=True)
class ToolMeta:
    name: str
    side_effect: bool
    signature: inspect.Signature


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._meta: dict[str, ToolMeta] = {}
        self.traces: list[dict[str, Any]] = []

    def tool(self, *, name: str, side_effect: bool = False):
        def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
            if name in self._tools:
                raise ValueError(f"重复工具：{name}")

            if inspect.iscoroutinefunction(function):
                @wraps(function)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return await function(*args, **kwargs)
                wrapped = async_wrapper
            else:
                @wraps(function)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return function(*args, **kwargs)
                wrapped = sync_wrapper

            self._tools[name] = wrapped
            self._meta[name] = ToolMeta(name, side_effect, inspect.signature(function))
            return wrapped
        return decorate

    def list_tools(self) -> tuple[ToolMeta, ...]:
        return tuple(self._meta.values())

    async def execute(self, name: str, *, request_id: str, **kwargs: Any) -> Any:
        function = self._tools[name]
        started = time.monotonic()
        trace = {"tool": name, "request_id": request_id, "ok": False}
        try:
            result = function(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            trace["ok"] = True
            return result
        except Exception as exc:
            trace["error_type"] = type(exc).__name__
            raise
        finally:
            trace["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
            self.traces.append(trace)


@contextmanager
def ndjson_batches(path: Path, *, batch_size: int, max_line: int = 10_000) -> Iterator[Iterator[list[dict[str, Any]]]]:
    if batch_size < 1:
        raise ValueError("batch_size 必须大于 0")
    file = path.open("r", encoding="utf-8")

    def generate() -> Iterator[list[dict[str, Any]]]:
        batch: list[dict[str, Any]] = []
        for line_number, line in enumerate(file, 1):
            if len(line) > max_line:
                raise ValueError(f"第 {line_number} 行过长")
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"第 {line_number} 行不是对象")
            if value.get("active") is False:
                continue
            batch.append(value)
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    try:
        yield generate()
    finally:
        file.close()


async def async_pipeline(source: AsyncIterator[dict[str, Any]], batch_size: int) -> AsyncIterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    try:
        async for item in source:
            batch.append(item)
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
    finally:
        close = getattr(source, "aclose", None)
        if close is not None:
            await close()

