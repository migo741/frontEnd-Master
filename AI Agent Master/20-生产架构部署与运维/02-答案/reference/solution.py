"""第 20 章：公平队列、provider 熔断与 Prompt canary 控制面。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import time
from typing import Callable


class TenantFairQueue:
    def __init__(self, per_tenant_limit: int = 100) -> None:
        self.per_tenant_limit = per_tenant_limit
        self.queues: dict[str, deque[str]] = {}
        self.rotation: deque[str] = deque()
        self.seen: set[str] = set()

    def enqueue(self, tenant_id: str, run_id: str) -> bool:
        if run_id in self.seen:
            return False
        queue = self.queues.setdefault(tenant_id, deque())
        if len(queue) >= self.per_tenant_limit:
            raise OverflowError("tenant queue limit reached")
        if not queue:
            self.rotation.append(tenant_id)
        queue.append(run_id)
        self.seen.add(run_id)
        return True

    def pop(self) -> tuple[str, str] | None:
        if not self.rotation:
            return None
        tenant_id = self.rotation.popleft()
        queue = self.queues[tenant_id]
        run_id = queue.popleft()
        if queue:
            self.rotation.append(tenant_id)
        return tenant_id, run_id


class CircuitOpen(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at: float | None = None

    def call(self, operation: Callable[[], str], now: float | None = None) -> str:
        current = time.monotonic() if now is None else now
        if self.opened_at is not None and current - self.opened_at < self.cooldown_seconds:
            raise CircuitOpen("provider circuit is open")
        if self.opened_at is not None:
            self.opened_at = None  # half-open probe
        try:
            result = operation()
        except Exception:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = current
            raise
        self.failures = 0
        return result


@dataclass
class PromptRelease:
    stable: str
    candidate: str
    candidate_percent: int = 5
    enabled: bool = True

    def select(self, run_id: str) -> str:
        bucket = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % 100
        return self.candidate if self.enabled and bucket < self.candidate_percent else self.stable

    def evaluate(self, stable_success: float, candidate_success: float, max_drop: float = .01) -> None:
        if candidate_success < stable_success - max_drop:
            self.enabled = False


def required_worker_capacity(peak_rps: float, p95_seconds: float, utilization: float = .7) -> int:
    if peak_rps <= 0 or p95_seconds <= 0 or not 0 < utilization < 1:
        raise ValueError("invalid capacity inputs")
    concurrent = peak_rps * p95_seconds / utilization
    return int(concurrent) + (concurrent % 1 > 0)

