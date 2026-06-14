"""In-memory response cache for the analysis pipeline.

Caches full analysis results keyed by (normalised_question, table_fingerprint)
so identical questions against the same schema return instantly without burning
LLM tokens.  The cache auto-invalidates when the database schema changes
(tables added/removed/modified).
"""

from __future__ import annotations

import hashlib
import re
import time
import threading
from dataclasses import dataclass, field
from typing import Any

from backend.database.connection import get_table_info


@dataclass
class CacheEntry:
    response: str
    charts: list[str]
    sql_results: list[str]
    steps: list[str]
    created_at: float = field(default_factory=time.time)


class ResponseCache:
    def __init__(self, max_size: int = 200, ttl_seconds: int = 3600):
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Key building
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(question: str) -> str:
        """Lowercase, collapse whitespace, strip punctuation at edges."""
        q = question.lower().strip()
        q = re.sub(r"\s+", " ", q)
        q = q.strip("?.! ")
        return q

    @staticmethod
    def _table_fingerprint() -> str:
        """Hash of current table names + row counts so cache invalidates on schema change."""
        try:
            tables = get_table_info()
            sig = "|".join(
                f"{t['name']}:{t.get('rows', 0)}:{t.get('columns', 0)}"
                for t in sorted(tables, key=lambda t: t["name"])
            )
        except Exception:
            sig = "__unknown__"
        return hashlib.md5(sig.encode()).hexdigest()

    def _make_key(self, question: str) -> str:
        norm = self._normalise(question)
        fp = self._table_fingerprint()
        return hashlib.sha256(f"{norm}||{fp}".encode()).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, question: str) -> CacheEntry | None:
        key = self._make_key(question)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() - entry.created_at > self._ttl:
                del self._store[key]
                return None
            return entry

    def put(
        self,
        question: str,
        response: str,
        charts: list[str],
        sql_results: list[str],
        steps: list[str] | None = None,
    ) -> None:
        key = self._make_key(question)
        entry = CacheEntry(
            response=response,
            charts=list(charts),
            sql_results=list(sql_results),
            steps=list(steps or []),
        )
        with self._lock:
            self._store[key] = entry
            if len(self._store) > self._max_size:
                oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                del self._store[oldest_key]

    def invalidate_all(self) -> int:
        """Drop every entry. Returns how many were removed."""
        with self._lock:
            n = len(self._store)
            self._store.clear()
            return n

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._store),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
            }
