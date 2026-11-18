"""Thread-safe storage of the latest scrape result."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._result: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._last_attempt: Optional[str] = None

    def update(self, result: dict) -> None:
        with self._lock:
            self._result = result
            self._last_error = None
            self._last_attempt = result.get("scraped_at") or _now()

    def update_error(self, error: str) -> None:
        with self._lock:
            self._last_error = error
            self._last_attempt = _now()

    def snapshot(self) -> dict:
        with self._lock:
            if self._result is None:
                return {
                    "status": "waiting",
                    "scraped_at": None,
                    "last_attempt": self._last_attempt,
                    "last_error": self._last_error,
                    "livebar_url": None,
                    "main_feed": None,
                    "feeds": [],
                    "articles": [],
                    "popular": [],
                    "breaking": [],
                    "errors": [],
                }
            snap = dict(self._result)
            snap["status"] = "degraded" if self._last_error else "ok"
            snap["last_attempt"] = self._last_attempt
            snap["last_error"] = self._last_error
            return snap
