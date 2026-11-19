"""Thread-safe storage of the latest scrape result."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

# A last successful update older than this is reported as a data-fetching
# problem (stale) in the UI and in /api/status.
STALE_AFTER_MINUTES = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def age_minutes(scraped_at: Optional[str]) -> Optional[int]:
    """Whole minutes since the last successful update (None = no data yet)."""
    if not scraped_at:
        return None
    try:
        then = datetime.fromisoformat(scraped_at)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - then
    return max(0, int(delta.total_seconds() // 60))


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._result: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._last_attempt: Optional[str] = None
        self._all_ok = True  # every enabled source succeeded in last scrape

    def update(self, result: dict) -> None:
        with self._lock:
            self._result = result
            self._last_error = None
            self._last_attempt = result.get("scraped_at") or _now()
            self._all_ok = result.get("all_ok", True)

    def update_error(self, error: str) -> None:
        with self._lock:
            self._last_error = error
            self._last_attempt = _now()

    def snapshot(self) -> dict:
        with self._lock:
            if self._result is None:
                return {
                    # no data yet, but a scrape was attempted and failed
                    "status": "waiting" if not self._last_error else "degraded",
                    "scraped_at": None,
                    "age_minutes": None,
                    "stale": False,
                    "last_attempt": self._last_attempt,
                    "last_error": self._last_error,
                    "sources": {},
                    "all_ok": True,
                    "livebar_url": None,
                    "main_feed": None,
                    "feeds": [],
                    "articles": [],
                    "popular": [],
                    "breaking": [],
                    "errors": [],
                }
            snap = dict(self._result)
            snap["status"] = "degraded" if (self._last_error or not self._all_ok) else "ok"
            snap["last_attempt"] = self._last_attempt
            snap["last_error"] = self._last_error
            age = age_minutes(self._result.get("scraped_at"))
            snap["age_minutes"] = age
            snap["stale"] = age is not None and age > STALE_AFTER_MINUTES
            return snap
