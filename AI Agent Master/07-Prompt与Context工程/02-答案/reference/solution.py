"""第 07 章：带信任、时效、敏感度和 token 预算的 Context Builder。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Trust(IntEnum):
    UNTRUSTED = 0
    USER = 1
    VERIFIED = 2
    POLICY = 3


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SECRET = "secret"


@dataclass(frozen=True)
class ContextItem:
    key: str
    text: str
    source: str
    trust: Trust
    sensitivity: Sensitivity
    tokens: int
    priority: int
    tenant_id: str
    fresh: bool = True


@dataclass(frozen=True)
class ContextManifest:
    included: tuple[ContextItem, ...]
    dropped: tuple[tuple[str, str], ...]
    used_tokens: int


def build_context(
    items: list[ContextItem],
    *,
    tenant_id: str,
    token_budget: int,
    allow_internal: bool,
) -> ContextManifest:
    included: list[ContextItem] = []
    dropped: list[tuple[str, str]] = []
    used = 0

    # 安全政策、优先级、信任和新鲜度决定稳定顺序；不让模型自由选择。
    ordered = sorted(items, key=lambda i: (-i.priority, -int(i.trust), not i.fresh, i.key))
    for item in ordered:
        if item.tenant_id != tenant_id:
            dropped.append((item.key, "tenant_mismatch"))
            continue
        if item.sensitivity is Sensitivity.SECRET:
            dropped.append((item.key, "secret_never_enters_model"))
            continue
        if item.sensitivity is Sensitivity.INTERNAL and not allow_internal:
            dropped.append((item.key, "internal_not_allowed"))
            continue
        if used + item.tokens > token_budget:
            dropped.append((item.key, "token_budget"))
            continue
        included.append(item)
        used += item.tokens
    return ContextManifest(tuple(included), tuple(dropped), used)


def render_for_model(manifest: ContextManifest) -> str:
    blocks = []
    for item in manifest.included:
        label = "INSTRUCTION" if item.trust is Trust.POLICY else "UNTRUSTED_DATA" if item.trust is Trust.UNTRUSTED else "DATA"
        blocks.append(f"<{label} source={item.source!r}>\n{item.text}\n</{label}>")
    return "\n\n".join(blocks)

