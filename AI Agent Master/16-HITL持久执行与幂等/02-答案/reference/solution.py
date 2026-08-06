"""第 16 章：SQLite durable runtime，演示 lease、fencing、HITL 与幂等。"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import sqlite3
import time
from typing import Iterator


class Conflict(RuntimeError):
    pass


def canonical_hash(value: dict[str, object]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class DurableStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs(
              id TEXT PRIMARY KEY, state TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
              lease_owner TEXT, lease_until REAL, fencing INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS events(
              run_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY(run_id, seq), FOREIGN KEY(run_id) REFERENCES runs(id)
            );
            CREATE TABLE IF NOT EXISTS proposals(
              id TEXT PRIMARY KEY, run_id TEXT NOT NULL, args TEXT NOT NULL, args_hash TEXT NOT NULL,
              expires_at REAL NOT NULL, status TEXT NOT NULL, approver TEXT
            );
            CREATE TABLE IF NOT EXISTS operations(
              operation_id TEXT PRIMARY KEY, result TEXT NOT NULL
            );
            """
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def create_run(self, run_id: str, state: dict[str, object]) -> None:
        self.db.execute(
            "INSERT INTO runs(id, state) VALUES (?, ?)",
            (run_id, json.dumps(state, ensure_ascii=False, sort_keys=True)),
        )

    def claim_run(self, run_id: str, worker: str, lease_seconds: float, now: float | None = None) -> int:
        current = time.time() if now is None else now
        with self.transaction():
            row = self.db.execute("SELECT lease_owner, lease_until, fencing FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise LookupError(run_id)
            if row["lease_until"] is not None and row["lease_until"] > current and row["lease_owner"] != worker:
                raise Conflict("run already leased")
            fencing = int(row["fencing"]) + 1
            self.db.execute(
                "UPDATE runs SET lease_owner=?, lease_until=?, fencing=? WHERE id=?",
                (worker, current + lease_seconds, fencing, run_id),
            )
        return fencing

    def append_event(
        self, run_id: str, worker: str, fencing: int, expected_version: int,
        kind: str, payload: dict[str, object], now: float | None = None,
    ) -> int:
        current = time.time() if now is None else now
        with self.transaction():
            row = self.db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if (
                row is None or row["lease_owner"] != worker or row["fencing"] != fencing
                or row["lease_until"] <= current
            ):
                raise Conflict("stale or expired worker lease")
            if row["version"] != expected_version:
                raise Conflict("optimistic version conflict")
            next_version = expected_version + 1
            self.db.execute(
                "INSERT INTO events(run_id, seq, kind, payload) VALUES (?, ?, ?, ?)",
                (run_id, next_version, kind, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
            self.db.execute("UPDATE runs SET version=?, state=? WHERE id=?", (
                next_version, json.dumps(payload, ensure_ascii=False, sort_keys=True), run_id
            ))
        return next_version

    def create_proposal(
        self, proposal_id: str, run_id: str, arguments: dict[str, object], expires_at: float
    ) -> str:
        args = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = canonical_hash(arguments)
        self.db.execute(
            "INSERT INTO proposals VALUES (?, ?, ?, ?, ?, 'pending', NULL)",
            (proposal_id, run_id, args, digest, expires_at),
        )
        return digest

    def approve(self, proposal_id: str, approver: str, expected_hash: str, now: float | None = None) -> None:
        current = time.time() if now is None else now
        with self.transaction():
            row = self.db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if row is None or row["status"] != "pending":
                raise Conflict("proposal is not pending")
            if row["expires_at"] <= current or row["args_hash"] != expected_hash:
                raise Conflict("proposal expired or changed")
            self.db.execute(
                "UPDATE proposals SET status='approved', approver=? WHERE id=?",
                (approver, proposal_id),
            )

    def execute_once(self, operation_id: str, effect: callable) -> str:
        existing = self.db.execute(
            "SELECT result FROM operations WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if existing:
            return str(existing["result"])
        # 真实外部 API 必须也接受 operation_id；否则 DB 提交前 crash 仍可能重复副作用。
        result = str(effect(operation_id))
        self.db.execute(
            "INSERT OR IGNORE INTO operations(operation_id, result) VALUES (?, ?)",
            (operation_id, result),
        )
        return str(self.db.execute(
            "SELECT result FROM operations WHERE operation_id=?", (operation_id,)
        ).fetchone()["result"])

