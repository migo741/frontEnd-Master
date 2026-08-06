"""第 21 章：带引用的研究 Agent 与代码补丁 policy。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable


class PolicyViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    text: str
    quality: float
    age_days: int


@dataclass(frozen=True)
class Claim:
    text: str
    source_url: str


@dataclass(frozen=True)
class ResearchResult:
    claims: tuple[Claim, ...]
    rejected_sources: tuple[str, ...]


Search = Callable[[str], list[Page]]


class ResearchAgent:
    INJECTION = re.compile(r"ignore (?:all |previous )?instructions|system prompt|输出密钥", re.I)

    def __init__(self, search: Search, max_sources: int = 5, max_age_days: int = 365) -> None:
        self.search, self.max_sources, self.max_age_days = search, max_sources, max_age_days

    def run(self, question: str) -> ResearchResult:
        pages = self.search(question)[: self.max_sources]
        claims: list[Claim] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for page in pages:
            if page.url in seen or page.quality < .6 or page.age_days > self.max_age_days or self.INJECTION.search(page.text):
                rejected.append(page.url)
                continue
            seen.add(page.url)
            for line in page.text.splitlines():
                if line.startswith("FACT:") and len(line[5:].strip()) >= 5:
                    claims.append(Claim(line[5:].strip(), page.url))
        return ResearchResult(tuple(claims), tuple(rejected))

    @staticmethod
    def verify_report(report: str, citations: dict[str, str], claims: tuple[Claim, ...]) -> None:
        for claim in claims:
            marker = next((name for name, url in citations.items() if url == claim.source_url), None)
            if marker is None or claim.text not in report or marker not in report:
                raise PolicyViolation(f"unsupported citation for claim: {claim.text}")


class PatchGuard:
    def __init__(self, max_changed_lines: int = 300) -> None:
        self.max_changed_lines = max_changed_lines

    def validate_diff(self, diff: str) -> list[str]:
        changed = sum(
            1 for line in diff.splitlines()
            if (line.startswith("+") and not line.startswith("+++"))
            or (line.startswith("-") and not line.startswith("---"))
        )
        if changed > self.max_changed_lines:
            raise PolicyViolation("diff exceeds review budget")
        paths: list[str] = []
        for line in diff.splitlines():
            if line.startswith("+++ b/") or line.startswith("--- a/"):
                path = line[6:]
                if path.startswith("/") or ".." in path.split("/") or path in {".env", ".git/config"}:
                    raise PolicyViolation("patch path is forbidden")
                paths.append(path)
        if not paths:
            raise PolicyViolation("no workspace patch found")
        return paths

    @staticmethod
    def validate_command(command: tuple[str, ...]) -> None:
        allowed = {("python", "-m", "unittest"), ("pytest",), ("npm", "test"), ("npm", "run", "lint")}
        if not any(command[: len(prefix)] == prefix for prefix in allowed):
            raise PolicyViolation("command is outside test allowlist")

