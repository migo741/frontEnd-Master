"""第 18 章：轻量 OpenTelemetry 风格 tracing、redaction 与成本门禁。"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import time
from typing import Iterator


SENSITIVE_KEYS = {"prompt", "body", "email", "token", "api_key", "secret"}


def redact(attributes: dict[str, object]) -> dict[str, object]:
    clean: dict[str, object] = {}
    for key, value in attributes.items():
        if key.casefold() in SENSITIVE_KEYS:
            clean[key] = "[REDACTED]"
        elif key == "tenant_id":
            clean[key] = hashlib.sha256(str(value).encode()).hexdigest()[:12]
        else:
            clean[key] = value
    return clean


@dataclass
class Span:
    name: str
    attributes: dict[str, object]
    start_ns: int = field(default_factory=time.monotonic_ns)
    end_ns: int | None = None
    status: str = "ok"
    events: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        end = self.end_ns or time.monotonic_ns()
        return (end - self.start_ns) / 1_000_000

    def event(self, name: str, **attributes: object) -> None:
        self.events.append((name, redact(attributes)))


class InMemoryExporter:
    def __init__(self) -> None:
        self.spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attributes: object) -> Iterator[Span]:
        current = Span(name, redact(attributes))
        try:
            yield current
        except BaseException as exc:
            current.status = "error"
            current.event("exception", type=type(exc).__name__)
            raise
        finally:
            current.end_ns = time.monotonic_ns()
            self.spans.append(current)


@dataclass(frozen=True)
class RunMetric:
    success: bool
    latency_ms: float
    cost_usd: float
    tool_errors: int = 0
    looped: bool = False


def summarize(runs: list[RunMetric]) -> dict[str, float]:
    if not runs:
        raise ValueError("runs cannot be empty")
    latencies = sorted(run.latency_ms for run in runs)
    successes = sum(run.success for run in runs)
    return {
        "success_rate": successes / len(runs),
        "p95_ms": latencies[max(0, int(.95 * len(latencies)) - 1)],
        "cost_per_success": sum(run.cost_usd for run in runs) / max(successes, 1),
        "tool_error_rate": sum(run.tool_errors for run in runs) / len(runs),
        "loop_rate": sum(run.looped for run in runs) / len(runs),
    }


def accept_cost_experiment(
    baseline: dict[str, float], candidate: dict[str, float],
    target_reduction: float = .5, max_quality_drop: float = .01,
) -> bool:
    quality_ok = candidate["success_rate"] >= baseline["success_rate"] - max_quality_drop
    cost_ok = candidate["cost_per_success"] <= baseline["cost_per_success"] * (1 - target_reduction)
    return quality_ok and cost_ok

