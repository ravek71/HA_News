"""Application settings.

Value priority: /data/options.json (Home Assistant app options) >
environment variables > defaults.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable

OPTIONS_FILE = "/data/options.json"


def _load_options() -> dict:
    try:
        with open(OPTIONS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _pick(options: dict, key: str, env: str, default: Any, cast: Callable[[Any], Any]) -> Any:
    if options.get(key) is not None:
        try:
            return cast(options[key])
        except (TypeError, ValueError):
            pass
    raw = os.environ.get(env)
    if raw not in (None, ""):
        try:
            return cast(raw)
        except (TypeError, ValueError):
            pass
    return default


class Settings:
    def __init__(self) -> None:
        options = _load_options()

        # 8099 is the Supervisor ingress port: the app gets a panel in the
        # HA sidebar (ingress: true) and is also exposed on host port 8080
        self.port = _pick(options, "port", "PORT", 8099, int)
        self.interval_minutes = _pick(options, "interval_minutes", "INTERVAL_MINUTES", 10, int)
        self.max_articles = _pick(options, "max_articles", "MAX_ARTICLES", 60, int)
        self.max_feeds = _pick(options, "max_feeds", "MAX_FEEDS", 12, int)
        self.timeout = _pick(options, "timeout", "TIMEOUT", 30, int)
        self.log_level = str(_pick(options, "log_level", "LOG_LEVEL", "INFO", str)).upper()

        self.feed_uuids = self._feed_uuids(options)

    @staticmethod
    def _feed_uuids(options: dict) -> list:
        value = options.get("feed_uuids")
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        raw = os.environ.get("FEED_UUIDS", "")
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()
