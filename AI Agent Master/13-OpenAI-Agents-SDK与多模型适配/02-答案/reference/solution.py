"""第 13 章：provider-neutral capability registry 与显式模型路由。"""

from __future__ import annotations

from dataclasses import dataclass, field


class NoEligibleModel(RuntimeError):
    """没有模型能在不降级语义/合规要求的前提下处理请求。"""


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: str
    capabilities: frozenset[str]
    regions: frozenset[str]
    cost_per_million: float
    p95_ms: int
    quality: float


@dataclass(frozen=True)
class TenantPolicy:
    tenant_id: str
    allowed_providers: frozenset[str]
    allowed_models: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RoutingRequest:
    required_capabilities: frozenset[str]
    region: str
    max_cost_per_million: float
    max_p95_ms: int
    minimum_quality: float = 0.0


class ModelRouter:
    def __init__(self, profiles: list[ModelProfile]) -> None:
        self.profiles = tuple(profiles)

    def route(self, request: RoutingRequest, policy: TenantPolicy) -> ModelProfile:
        eligible = [
            model
            for model in self.profiles
            if request.required_capabilities <= model.capabilities
            and request.region in model.regions
            and model.provider in policy.allowed_providers
            and (not policy.allowed_models or model.name in policy.allowed_models)
            and model.cost_per_million <= request.max_cost_per_million
            and model.p95_ms <= request.max_p95_ms
            and model.quality >= request.minimum_quality
        ]
        if not eligible:
            raise NoEligibleModel(
                "no model satisfies capability, region, policy, quality, cost and latency together"
            )
        # 质量过线后优先成本，再比较延迟和质量；规则可被 eval 结果替换。
        return min(eligible, key=lambda m: (m.cost_per_million, m.p95_ms, -m.quality))


class PolicyToolExecutor:
    """路由成功不等于获准执行工具；权限检查必须独立存在。"""

    def __init__(self, grants: dict[str, set[str]]) -> None:
        self.grants = grants

    def execute(self, principal: str, tool: str, **arguments: object) -> dict[str, object]:
        if tool not in self.grants.get(principal, set()):
            raise PermissionError(f"{principal} cannot call {tool}")
        return {"tool": tool, "arguments": arguments, "principal": principal}

