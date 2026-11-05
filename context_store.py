"""Local SQLite storage for bounded context and explicitly approved memory."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SENSITIVE = re.compile(
    r"(api[_ -]?key|secret|password|passwd|token|private[_ -]?key|authorization)\s*[:=]",
    re.IGNORECASE,
)


class ContextStore:
    """SQLite store separating current context, history, preferences, and projects."""

    def __init__(self, path: str | Path | None = None, history_limit: int = 40) -> None:
        configured = path or os.getenv("TROJAN_CONTEXT_PATH", "")
        default = Path(os.getenv("APPDATA", Path.home())) / "Trojan AI" / "context.db"
        self.path = Path(configured) if configured else default
        if self.path.suffix.lower() != ".db":
            self.path = self.path.with_suffix(".db")
        self.history_limit = max(4, history_limit)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._create_schema()
        self._migrate_json_if_needed(configured)

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id TEXT PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
                    created_at TEXT NOT NULL, metadata TEXT
                );
                CREATE TABLE IF NOT EXISTS approved_memory (
                    id TEXT PRIMARY KEY, category TEXT NOT NULL, content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, content TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS conversation_created_idx
                    ON conversation_history(created_at);
                CREATE INDEX IF NOT EXISTS memory_category_idx
                    ON approved_memory(category);
                """
            )

    def _migrate_json_if_needed(self, configured: str | Path | None) -> None:
        if configured and Path(configured).suffix.lower() == ".json":
            source = Path(configured)
        elif configured:
            return
        else:
            source = self.path.with_name("context.json")
        if not source.exists() or self._connection.execute("SELECT 1 FROM conversation_history LIMIT 1").fetchone():
            return
        try:
            loaded = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        with self._connection:
            for item in loaded.get("conversation", []):
                if item.get("role") in {"user", "assistant", "tool"} and isinstance(item.get("content"), str):
                    self._connection.execute(
                        "INSERT OR IGNORE INTO conversation_history VALUES (?, ?, ?, ?, ?)",
                        (item.get("id", str(uuid.uuid4())), item["role"], item["content"],
                         item.get("created_at", _now()), json.dumps(item.get("metadata")) if item.get("metadata") else None),
                    )
            for item in loaded.get("memories", []):
                if isinstance(item.get("content"), str):
                    self._connection.execute(
                        "INSERT OR IGNORE INTO approved_memory VALUES (?, ?, ?, ?)",
                        (item.get("id", str(uuid.uuid4())), item.get("category", "preference"),
                         item["content"], item.get("created_at", _now())),
                    )

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @staticmethod
    def _check_content(content: str, limit: int) -> str:
        clean = content.strip()
        if not clean or len(clean) > limit:
            raise ValueError(f"Content must be between 1 and {limit} characters.")
        if _SENSITIVE.search(clean):
            raise ValueError("Secrets and credential-like information cannot be saved.")
        return clean

    def conversation(self) -> list[dict[str, str]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT role, content FROM conversation_history ORDER BY rowid DESC LIMIT ?",
                (self.history_limit,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def history(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, role, content, created_at, metadata FROM conversation_history "
                "ORDER BY rowid DESC LIMIT ?", (limit,),
            ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            if item["metadata"]:
                item["metadata"] = json.loads(item["metadata"])
            result.append(item)
        return result

    def append_turn(self, role: str, content: str, *, metadata: dict[str, Any] | None = None) -> None:
        if role not in {"user", "assistant", "tool"}:
            raise ValueError("Invalid conversation turn.")
        clean = self._check_content(content, 20_000)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO conversation_history VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), role, clean, _now(), json.dumps(metadata) if metadata else None),
            )
            self._connection.execute(
                "DELETE FROM conversation_history WHERE rowid NOT IN "
                "(SELECT rowid FROM conversation_history ORDER BY rowid DESC LIMIT ?)",
                (max(self.history_limit * 5, 200),),
            )

    def clear_conversation(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM conversation_history")

    def memories(self, category: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT id, category, content, created_at FROM approved_memory"
        args: tuple[Any, ...] = ()
        if category:
            query += " WHERE category = ?"
            args = (category,)
        query += " ORDER BY rowid"
        with self._lock:
            return [dict(row) for row in self._connection.execute(query, args).fetchall()]

    def add_memory(self, content: str, category: str = "preference") -> dict[str, Any]:
        clean = self._check_content(content, 2_000)
        category = category.strip()[:100] or "preference"
        if category not in {"preference", "project"}:
            raise ValueError("Memory category must be preference or project.")
        entry = {"id": str(uuid.uuid4()), "content": clean, "category": category, "created_at": _now()}
        with self._lock, self._connection:
            self._connection.execute("INSERT INTO approved_memory VALUES (?, ?, ?, ?)",
                                     (entry["id"], category, clean, entry["created_at"]))
        return entry

    def delete_memory(self, memory_id: str) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute("DELETE FROM approved_memory WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    def clear_memories(self, category: str | None = None) -> None:
        with self._lock, self._connection:
            if category:
                self._connection.execute("DELETE FROM approved_memory WHERE category = ?", (category,))
            else:
                self._connection.execute("DELETE FROM approved_memory")

    def projects(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._connection.execute(
                "SELECT id, name, content, created_at, updated_at FROM projects ORDER BY name"
            ).fetchall()]

    def save_project(self, name: str, content: str) -> dict[str, Any]:
        clean_name = self._check_content(name, 120)
        clean_content = self._check_content(content, 4_000)
        now = _now()
        project = {"id": str(uuid.uuid4()), "name": clean_name, "content": clean_content, "created_at": now, "updated_at": now}
        with self._lock, self._connection:
            existing = self._connection.execute("SELECT id, created_at FROM projects WHERE name = ?", (clean_name,)).fetchone()
            if existing:
                project["id"], project["created_at"] = existing["id"], existing["created_at"]
                self._connection.execute("UPDATE projects SET content = ?, updated_at = ? WHERE id = ?",
                                         (clean_content, now, existing["id"]))
            else:
                self._connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                                         (project["id"], clean_name, clean_content, now, now))
        return project

    def delete_project(self, project_id: str) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0
