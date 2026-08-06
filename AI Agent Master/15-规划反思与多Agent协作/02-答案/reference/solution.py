"""第 15 章：可测试、有限预算、最小权限的多 Agent 研究编排。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Evidence:
    source_id: str
    claim: str
    supports: bool


@dataclass(frozen=True)
class WorkerTask:
    id: str
    query: str
    capabilities: frozenset[str] = frozenset({"search:read"})


@dataclass
class WorkerResult:
    task_id: str
    evidence: list[Evidence] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class ResearchReport:
    answer: str
    citations: tuple[str, ...]
    conflicts: tuple[str, ...]
    failed_tasks: tuple[str, ...]


class Planner:
    def __init__(self, max_workers: int = 3) -> None:
        self.max_workers = max_workers

    def plan(self, question: str) -> list[WorkerTask]:
        aspects = [part.strip() for part in question.split("、") if part.strip()]
        return [WorkerTask(f"task-{index}", aspect) for index, aspect in enumerate(aspects[: self.max_workers], 1)]


Search = Callable[[str], list[Evidence]]


class ResearchOrchestrator:
    def __init__(self, search: Search, max_workers: int = 3, max_total_searches: int = 3) -> None:
        self.search = search
        self.planner = Planner(max_workers)
        self.max_total_searches = max_total_searches

    def run(self, question: str) -> ResearchReport:
        tasks = self.planner.plan(question)[: self.max_total_searches]
        results: list[WorkerResult] = []
        for task in tasks:
            if task.capabilities != frozenset({"search:read"}):
                results.append(WorkerResult(task.id, error="worker capability violation"))
                continue
            try:
                results.append(WorkerResult(task.id, self.search(task.query)))
            except Exception as exc:  # worker failure becomes data, not supervisor loop
                results.append(WorkerResult(task.id, error=f"{type(exc).__name__}: {exc}"))

        by_claim: dict[str, list[Evidence]] = {}
        for result in results:
            for item in result.evidence:
                by_claim.setdefault(item.claim, []).append(item)

        supported: list[str] = []
        conflicts: list[str] = []
        citations: set[str] = set()
        for claim, evidence in by_claim.items():
            votes = {item.supports for item in evidence}
            citations.update(item.source_id for item in evidence)
            if votes == {True}:
                supported.append(claim)
            elif len(votes) > 1:
                conflicts.append(claim)

        answer = "；".join(sorted(supported)) if supported else "证据不足，不能作答"
        return ResearchReport(
            answer=answer,
            citations=tuple(sorted(citations)),
            conflicts=tuple(sorted(conflicts)),
            failed_tasks=tuple(result.task_id for result in results if result.error),
        )


@dataclass(frozen=True)
class AgentRole:
    name: str
    capabilities: frozenset[str]


class RefundExecutor:
    def execute(self, role: AgentRole, approval: bool, operation_id: str) -> str:
        if "refund:execute" not in role.capabilities or not approval:
            raise PermissionError("only approved executor may refund")
        return operation_id

