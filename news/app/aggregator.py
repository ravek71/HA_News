"""Runs all enabled news sources and merges their results.

Each source (``OnetScraper`` / ``WpScraper``) returns Article objects.
The aggregator:

* runs the enabled sources in parallel (one thread each), so a slow or
  failing source does not delay the others,
* merges the "breaking" lists by publication time (newest first),
* merges the rankings by alternating items (onet #1, wp #1, onet #2, ...)
  so every enabled source has a fair share of the top list,
* collects per-source status for ``/api/status``.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from .config import Settings
from .models import Article
from .onet_scraper import OnetScraper
from .wp_scraper import WpScraper

log = logging.getLogger(__name__)

# canonical order: onet is the original (primary) source
SOURCES = ("onet", "wp")


def _interleave(a: list, b: list, limit: int) -> list:
    """Round-robin merge of two ranked lists (a[0], b[0], a[1], b[1], ...)."""
    out: list = []
    ia = ib = 0
    while ia < len(a) or ib < len(b):
        if ia < len(a):
            out.append(a[ia])
            ia += 1
        if ib < len(b):
            out.append(b[ib])
            ib += 1
        if len(out) >= limit:
            break
    return out


def _breaking_key(article: Article) -> float:
    """Minutes since publication (smaller = newer); untimed items last."""
    minutes = getattr(article, "_sort_min", None)
    return minutes if isinstance(minutes, (int, float)) else float("inf")


class Aggregator:
    """Scrapes all enabled sources and merges them into one result."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scrapers = {"onet": OnetScraper(settings), "wp": WpScraper(settings)}

    def scrape(self) -> dict:
        enabled = self.settings.enabled_sources
        if not enabled:
            raise ValueError(
                "brak aktywnych źródeł — włącz enable_onet i/lub enable_wp w opcjach"
            )

        results: dict = {}
        failed: dict = {}
        lock = threading.Lock()

        def run(name: str) -> None:
            try:
                results[name] = self.scrapers[name].scrape()
            except Exception as exc:  # noqa: BLE001 - isolate source failures
                log.warning("scrape: source %s failed: %s", name, exc)
                with lock:
                    failed[name] = str(exc)

        threads = [threading.Thread(target=run, args=(name,), name=f"scrape-{name}") for name in enabled]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        errors = [f"{name}: {msg}" for name, msg in failed.items()]
        for name in enabled:
            if name in results:
                errors.extend(f"{name}: {msg}" for msg in results[name].get("errors", []))

        # per-source status (all sources, enabled or not)
        sources_status = {}
        for name in SOURCES:
            if name not in enabled:
                sources_status[name] = {
                    "enabled": False,
                    "ok": None,
                    "error": None,
                    "articles": 0,
                    "breaking": 0,
                }
            elif name in failed:
                sources_status[name] = {
                    "enabled": True,
                    "ok": False,
                    "error": failed[name],
                    "articles": 0,
                    "breaking": 0,
                }
            else:
                result = results[name]
                sources_status[name] = {
                    "enabled": True,
                    "ok": True,
                    "error": None,
                    "articles": len(result.get("articles", [])),
                    "breaking": len(result.get("breaking", [])),
                }

        # merged breaking: newest first (stable sort keeps per-source order
        # for items without a parseable time)
        breaking: list = []
        for name in enabled:
            if name in results:
                breaking.extend(results[name].get("breaking", []))
        breaking.sort(key=_breaking_key)

        # merged ranking: alternate between sources. Breaking items are kept
        # out of the ranking (they have their own section/page) so the ranking
        # shows each source's actual "top articles" list.
        onet_articles = [
            a for a in results.get("onet", {}).get("articles", []) if not a.breaking
        ]
        wp_articles = [
            a for a in results.get("wp", {}).get("articles", []) if not a.breaking
        ]
        ranked = _interleave(onet_articles, wp_articles, self.settings.max_articles)

        # "popular" stays the Onet main feed (documented as Onet-specific)
        popular = results.get("onet", {}).get("popular", [])

        return {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "sources": sources_status,
            "all_ok": not failed,
            "livebar_url": results.get("onet", {}).get("livebar_url"),
            "main_feed": results.get("onet", {}).get("main_feed"),
            "feeds": results.get("onet", {}).get("feeds", []),
            "articles": [a.to_dict() for a in ranked],
            "popular": [a.to_dict() for a in popular],
            "breaking": [a.to_dict() for a in breaking],
            "errors": errors,
        }
