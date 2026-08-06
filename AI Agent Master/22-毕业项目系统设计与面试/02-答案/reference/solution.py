"""第 22 章：Enterprise Operations Copilot 的可运行安全纵向切片。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import time
from typing import Callable


class DomainError(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    tenant_id: str
    text: str
    trusted: bool = True


class KnowledgeBase:
    def __init__(self, documents: list[KnowledgeDocument]) -> None:
        self.documents = documents

    def search(self, tenant_id: str, query: str, limit: int = 3) -> list[KnowledgeDocument]:
        terms = {term.casefold() for term in query.split() if len(term) > 1}
        rows = [
            document for document in self.documents
            if document.tenant_id == tenant_id and document.trusted
            and (not terms or any(term in document.text.casefold() for term in terms))
        ]
        return rows[:limit]


class RateLimited(RuntimeError):
    pass


class ModelGateway:
    def __init__(self, providers: list[Callable[[str], str]]) -> None:
        self.providers = providers

    def complete(self, prompt: str) -> str:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider(prompt)
            except RateLimited as exc:
                errors.append(str(exc))
        raise DomainError(f"all evaluated providers unavailable: {errors}")


def canonical_hash(value: dict[str, object]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class RefundProposal:
    id: str
    tenant_id: str
    arguments: dict[str, object]
    arguments_hash: str
    expires_at: float
    approved_by: str | None = None


class RefundWorkflow:
    def __init__(self) -> None:
        self.proposals: dict[str, RefundProposal] = {}
        self.operations: dict[str, str] = {}
        self.external_calls: list[str] = []

    def propose(self, principal: Principal, proposal_id: str, order_id: str, amount: int, now: float) -> RefundProposal:
        if "refund:propose" not in principal.scopes or amount <= 0:
            raise DomainError("proposal forbidden or invalid")
        arguments: dict[str, object] = {"order_id": order_id, "amount": amount}
        proposal = RefundProposal(
            proposal_id, principal.tenant_id, arguments, canonical_hash(arguments), now + 3600
        )
        self.proposals[proposal_id] = proposal
        return proposal

    def approve_and_execute(
        self, principal: Principal, proposal_id: str, expected_hash: str,
        operation_id: str, now: float,
    ) -> str:
        proposal = self.proposals.get(proposal_id)
        if proposal is None or proposal.tenant_id != principal.tenant_id:
            raise DomainError("proposal not found")
        if "refund:approve" not in principal.scopes or proposal.expires_at <= now:
            raise DomainError("approval forbidden or expired")
        if expected_hash != proposal.arguments_hash or canonical_hash(proposal.arguments) != expected_hash:
            raise DomainError("proposal arguments changed")
        if operation_id in self.operations:
            return self.operations[operation_id]
        proposal.approved_by = principal.user_id
        self.external_calls.append(operation_id)
        result = f"refund-{proposal.arguments['order_id']}"
        self.operations[operation_id] = result
        return result


class EnterpriseCopilot:
    def __init__(self, knowledge: KnowledgeBase, gateway: ModelGateway, refunds: RefundWorkflow) -> None:
        self.knowledge, self.gateway, self.refunds = knowledge, gateway, refunds

    def answer(self, principal: Principal, question: str) -> dict[str, object]:
        if "knowledge:read" not in principal.scopes:
            raise DomainError("knowledge access forbidden")
        evidence = self.knowledge.search(principal.tenant_id, question)
        if not evidence:
            return {"answer": "证据不足", "citations": []}
        manifest = [{"id": row.id, "text": row.text[:1_000]} for row in evidence]
        answer = self.gateway.complete(json.dumps(manifest, ensure_ascii=False))
        return {"answer": answer, "citations": [row.id for row in evidence]}


@dataclass(frozen=True)
class CapstoneEvalCase:
    id: str
    slice: str
    expected_control: str


def build_capstone_eval(size: int = 150) -> list[CapstoneEvalCase]:
    slices = [
        ("rag", "citation"), ("approval", "human_approval"), ("idempotency", "operation_id"),
        ("injection", "untrusted_data"), ("cross_tenant", "tenant_filter"),
        ("provider_429", "evaluated_fallback"),
    ]
    return [CapstoneEvalCase(f"cap-{i + 1:03d}", *slices[i % len(slices)]) for i in range(size)]


def eval_jsonl(size: int = 150) -> str:
    return "\n".join(json.dumps(asdict(case), ensure_ascii=False) for case in build_capstone_eval(size)) + "\n"

