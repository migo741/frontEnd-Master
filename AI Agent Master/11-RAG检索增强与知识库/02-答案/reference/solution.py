"""第 11 章：零外部依赖的 hybrid RAG 基线、ACL 与引用验证。"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass


TOKEN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    output: list[str] = []
    for token in TOKEN.findall(text):
        token = token.casefold()
        if all("\u4e00" <= char <= "\u9fff" for char in token):
            # 零依赖中文基线：字符 + bigram。生产环境替换为正式分词器。
            output.extend(token)
            output.extend(token[index:index + 2] for index in range(len(token) - 1))
        else:
            output.append(token)
    return output


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    tenant_id: str
    version: int
    title: str
    text: str
    allowed_roles: frozenset[str]


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class HybridIndex:
    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}

    def upsert(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk

    def delete_document(self, tenant_id: str, document_id: str) -> None:
        self._chunks = {key: value for key, value in self._chunks.items() if not (value.tenant_id == tenant_id and value.document_id == document_id)}

    def search(self, query: str, *, tenant_id: str, roles: frozenset[str], top_k: int = 5) -> list[Hit]:
        q_tokens = tokenize(query)
        q_set = set(q_tokens)
        candidates = [c for c in self._chunks.values() if c.tenant_id == tenant_id and (not c.allowed_roles or c.allowed_roles & roles)]
        document_frequency = Counter(token for c in candidates for token in set(tokenize(c.text)))
        scored: list[Hit] = []
        for chunk in candidates:
            tokens = tokenize(chunk.text)
            counts = Counter(tokens)
            lexical = sum(counts[t] * (math.log((len(candidates) + 1) / (document_frequency[t] + 1)) + 1) for t in q_tokens)
            semantic = len(q_set & set(tokens)) / max(1, len(q_set | set(tokens)))
            scored.append(Hit(chunk, lexical + semantic))
        return sorted((hit for hit in scored if hit.score > 0), key=lambda h: (-h.score, h.chunk.chunk_id))[:top_k]


@dataclass(frozen=True)
class Claim:
    text: str
    citation_ids: tuple[str, ...]


def validate_citations(claims: list[Claim], hits: list[Hit]) -> None:
    available = {hit.chunk.chunk_id: hit.chunk for hit in hits}
    for claim in claims:
        if not claim.citation_ids:
            raise ValueError("claim 缺少引用")
        for citation in claim.citation_ids:
            chunk = available.get(citation)
            if chunk is None:
                raise ValueError(f"未知引用：{citation}")
            # 最小确定性支持校验；生产再叠加人工/语义 grader。
            claim_tokens = set(tokenize(claim.text))
            chunk_tokens = set(tokenize(chunk.text))
            claim_bigrams = {
                token for token in claim_tokens
                if len(token) == 2 and all("\u4e00" <= char <= "\u9fff" for char in token)
            }
            supported = bool((claim_bigrams or claim_tokens) & chunk_tokens)
            if not supported:
                raise ValueError(f"引用不支持 claim：{citation}")
