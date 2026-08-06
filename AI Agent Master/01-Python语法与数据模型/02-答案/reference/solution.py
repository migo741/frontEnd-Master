"""第 01 章：无共享可变状态的 SessionStore 与事件归一化。"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


class SessionNotFound(KeyError):
    pass


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class SessionSnapshot:
    messages: tuple[dict[str, Any], ...]
    meta: dict[str, Any]


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create(self, session_id: str, messages: list[dict[str, Any]] | None = None) -> None:
        if not session_id or session_id in self._sessions:
            raise ValueError("session_id 必须非空且唯一")
        self._sessions[session_id] = {
            "messages": deepcopy(messages) if messages is not None else [],
            "meta": {"retries": 0},
        }

    def _get(self, session_id: str) -> dict[str, Any]:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFound(session_id) from exc

    def get(self, session_id: str) -> SessionSnapshot:
        value = self._get(session_id)
        return SessionSnapshot(tuple(deepcopy(value["messages"])), deepcopy(value["meta"]))

    def append(self, session_id: str, message: dict[str, Any]) -> None:
        if not isinstance(message, dict) or "role" not in message:
            raise ValueError("message 必须包含 role")
        self._get(session_id)["messages"].append(deepcopy(message))

    def update_meta(self, session_id: str, key: str, value: Any) -> None:
        if not key:
            raise ValueError("meta key 不能为空")
        self._get(session_id)["meta"][key] = deepcopy(value)

    def delete(self, session_id: str) -> None:
        self._get(session_id)
        del self._sessions[session_id]

    def dumps(self) -> str:
        return json.dumps({"version": 1, "sessions": self._sessions}, ensure_ascii=False)

    @classmethod
    def loads(cls, raw: str) -> "SessionStore":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProtocolError("不是合法 JSON") from exc
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ProtocolError("不支持的 store 版本")
        sessions = data.get("sessions")
        if not isinstance(sessions, dict):
            raise ProtocolError("sessions 必须是对象")
        store = cls()
        for session_id, value in sessions.items():
            if not isinstance(session_id, str) or not isinstance(value, dict):
                raise ProtocolError("损坏的 session")
            messages, meta = value.get("messages"), value.get("meta")
            if not isinstance(messages, list) or not isinstance(meta, dict):
                raise ProtocolError("损坏的 messages/meta")
            store._sessions[session_id] = deepcopy(value)
        return store


def normalize_event(provider: str, raw: dict[str, Any]) -> dict[str, Any]:
    """把三个示例供应商事件转换成统一事件；不修改 raw。"""
    event = deepcopy(raw)
    try:
        if provider == "alpha" and event.get("kind") == "delta":
            return {"type": "text_delta", "text": str(event["text"])}
        if provider == "beta" and event.get("type") == "function":
            return {
                "type": "tool_call",
                "call_id": str(event["id"]),
                "name": str(event["name"]),
                "arguments": deepcopy(event["arguments"]),
            }
        if provider == "gamma" and event.get("done") is True:
            return {"type": "completed", "usage": deepcopy(event.get("usage", {}))}
    except (KeyError, TypeError) as exc:
        raise ProtocolError(f"{provider} 事件缺少字段") from exc
    raise ProtocolError(f"未知事件：provider={provider}, keys={sorted(event)}")

