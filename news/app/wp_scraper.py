"""Web scraper for WP.pl (Wirtualna Polska) news.

Data sources (all public; the same ones the wp.pl main page uses):

1. Homepage https://www.wp.pl/
   - server-side rendered teasers with a ``data-bdbd`` JSON attribute;
     category "600" is the main stream (the WP equivalent of Onet's
     "O tym się mówi" ranking).
2. "Najnowsze" timeline on https://wiadomosci.wp.pl/
   - SSR list with ``<time datetime="...">`` publication timestamps
     (the WP equivalent of Onet's livebar breaking news).

No JavaScript and no private API is needed: everything below is plain
static HTML, just like for onet.pl.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .models import Article
from .onet_scraper import SKIP_TITLE_MARKERS, clean_url

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HOME_URL = "https://www.wp.pl/"
NEWS_URL = "https://wiadomosci.wp.pl/"
MAIN_CATEGORY = "600"  # id of the main stream on the wp.pl homepage
MAX_TIMELINE_ITEMS = 40

# first URL path segments are usually slugs, so categories come from the host
WP_DOMAIN_CATEGORIES = {
    "sportowefakty.wp.pl": "sport",
    "finanse.wp.pl": "finanse",
    "wiadomosci.wp.pl": "wiadomości",
    "informacje.wp.pl": "wiadomości",
    "autokult.pl": "motoryzacja",
    "dobreprogramy.pl": "technologia",
    "money.pl": "finanse",
    "benchmark.pl": "biznes",
    "kobieta.wp.pl": "lifestyle",
    "pogoda.wp.pl": "pogoda",
    "abczdrowie.pl": "zdrowie",
    "chcebyc.fit": "zdrowie",
    "haloursyn.pl": "motoryzacja",
    "rynekpierwotny.pl": "dom i ogród",
    "secrety.pl": "sekrety",
}


def wp_category_from_url(url: str) -> Optional[str]:
    """Derive a human-readable category from a WP.pl article URL."""
    if not url:
        return None
    try:
        host = (urlparse(url).netloc or "").lower().removeprefix("www.")
    except ValueError:
        return None
    return WP_DOMAIN_CATEGORIES.get(host)


class WpScraper:
    """Fetches and cleans WP.pl news (main stream + 'Najnowsze' timeline)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
            }
        )

    def _get_text(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.settings.timeout)
        resp.raise_for_status()
        return resp.content.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # homepage: main stream (category 600)
    # ------------------------------------------------------------------
    def _parse_home(self, html: str) -> list:
        """Extract the main-stream teasers (server-side rendered)."""
        soup = BeautifulSoup(html, "html.parser")
        out: list = []
        seen = set()
        for anchor in soup.find_all("a", href=True):
            raw = anchor.get("data-bdbd")
            if not raw:
                continue
            try:
                meta = json.loads(raw)
            except ValueError:
                continue
            if meta.get("type") not in ("sgTeaser", "sgTextlink"):
                continue
            if meta.get("categoryId") != MAIN_CATEGORY:
                continue

            href = (anchor.get("href") or "").strip()
            if not href.startswith("http"):
                continue

            title_el = anchor.select_one("h3.wp-teaser-title") or anchor.select_one(
                ".wp-text-link-title"
            )
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title:
                continue
            if any(marker in title.lower() for marker in SKIP_TITLE_MARKERS):
                continue
            # "Mat. Promocyjny" / "Materiał promocyjny" sponsored teasers
            if anchor.select_one(".wp-teaser-sponsored-label"):
                continue

            href = clean_url(href)
            if href in seen:
                continue
            seen.add(href)

            img = anchor.select_one("img")
            image = (img.get("src") or None) if img else None
            dot_params = meta.get("dotParams")
            ctype = dot_params.get("ctype") if isinstance(dot_params, dict) else None

            out.append(
                Article(
                    title=title,
                    url=href,
                    image=image,
                    site="wp",
                    section="Strumień główny",
                    category=wp_category_from_url(href),
                    kind="video" if ctype == "video" else "article",
                )
            )
        return out

    # ------------------------------------------------------------------
    # "Najnowsze" timeline (breaking-news equivalent)
    # ------------------------------------------------------------------
    def _parse_timeline(self, html: str) -> list:
        """Extract the 'Najnowsze' timeline entries with <time datetime>."""
        soup = BeautifulSoup(html, "html.parser")
        now = datetime.now(timezone.utc)
        out: list = []
        seen = set()
        for anchor in soup.select("a.timeline-entry"):
            if len(out) >= MAX_TIMELINE_ITEMS:
                break
            href = (anchor.get("href") or "").strip()
            if not href.startswith("http"):
                continue
            time_el = anchor.select_one("time")
            if time_el is None:
                continue
            iso = time_el.get("datetime") or ""
            display = time_el.get_text(strip=True) or iso
            h3 = anchor.select_one("h3")
            title = h3.get_text(" ", strip=True) if h3 else ""
            if not title:
                full = anchor.get_text(" ", strip=True)
                if display and full.startswith(display):
                    title = full[len(display):].strip(" \t:|–-")
            if not title:
                continue

            href = clean_url(href)
            if href in seen:
                continue
            seen.add(href)

            item = Article(
                title=title,
                url=href,
                site="wp",
                section="Najnowsze (pilne)",
                category=wp_category_from_url(href),
                kind="live",
                breaking=True,
                published=display or None,
            )
            # sortable key for the cross-source merge (minutes since "now")
            try:
                dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                item._sort_min = max(0.0, (now - dt).total_seconds() / 60.0)
            except ValueError:
                item._sort_min = None
            out.append(item)
        return out

    # ------------------------------------------------------------------
    # orchestration
    # ------------------------------------------------------------------
    def scrape(self) -> dict:
        errors: list = []
        articles: list = []
        breaking: list = []

        try:
            home = self._get_text(HOME_URL)
            articles = self._parse_home(home)
            log.info("wp: main stream articles: %d", len(articles))
        except Exception as exc:  # noqa: BLE001 - one bad source must not kill the scrape
            log.warning("wp: homepage failed: %s", exc)
            errors.append(f"strona główna: {exc}")

        try:
            news = self._get_text(NEWS_URL)
            breaking = self._parse_timeline(news)
            log.info("wp: 'najnowsze' timeline items: %d", len(breaking))
        except Exception as exc:  # noqa: BLE001
            log.warning("wp: 'najnowsze' timeline failed: %s", exc)
            errors.append(f"najnowsze: {exc}")

        return {"articles": articles, "breaking": breaking, "errors": errors}
