"""第 19 章：SSRF/path/archive/output policy 与演示级受限 Python runner。"""

from __future__ import annotations

import ast
import ipaddress
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


class SecurityViolation(RuntimeError):
    pass


def validate_url(url: str, resolved_ips: list[str]) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise SecurityViolation("only credential-free http(s) URLs are allowed")
    if parts.port not in {None, 80, 443}:
        raise SecurityViolation("port is not allowed")
    for raw in resolved_ips:
        address = ipaddress.ip_address(raw)
        if not address.is_global:
            raise SecurityViolation("DNS resolved to a non-public address")
    return url


def safe_workspace_path(workspace: Path, requested: str) -> Path:
    root = workspace.resolve()
    candidate = (root / requested).resolve()
    if candidate != root and root not in candidate.parents:
        raise SecurityViolation("path escapes workspace")
    return candidate


def validate_archive(entries: list[tuple[str, int, int]], max_files: int = 100, max_unpacked: int = 10_000_000) -> None:
    if len(entries) > max_files:
        raise SecurityViolation("too many archive entries")
    total = 0
    for name, unpacked, packed in entries:
        safe_workspace_path(Path("/sandbox"), name)
        if unpacked < 0 or packed < 0 or (packed and unpacked / packed > 100):
            raise SecurityViolation("suspicious compression ratio")
        total += unpacked
    if total > max_unpacked:
        raise SecurityViolation("archive exceeds unpacked budget")


FORBIDDEN_NODES = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input"}


def validate_demo_code(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise SecurityViolation(f"forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_CALLS:
            raise SecurityViolation(f"forbidden name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise SecurityViolation("dunder traversal is forbidden")


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_000_000, 1_000_000))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))


def run_demo_code(code: str, timeout_seconds: float = 1, max_output: int = 10_000) -> str:
    """演示级防误用 runner，不是恶意代码的安全边界。"""
    validate_demo_code(code)
    with tempfile.TemporaryDirectory(prefix="agent-demo-") as directory:
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", code], cwd=directory, env={},
                stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout_seconds,
                preexec_fn=_limits, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SecurityViolation("execution timeout") from exc
    output = result.stdout + result.stderr
    if len(output) > max_output:
        raise SecurityViolation("output limit exceeded")
    if result.returncode != 0:
        raise SecurityViolation(f"process failed with code {result.returncode}")
    return output.decode("utf-8", errors="replace")

