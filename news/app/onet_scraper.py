"""Web scraper for Onet.pl news.

Data sources (all public; the same ones the onet.pl main page uses):

1. Homepage https://www.onet.pl/
   - discovers the livebar (breaking news) iframe URL,
   - discovers the feed UUIDs of the main page sections.
2. Feed API https://mp-feed-api.onet.pl/2.0/feeds/<uuid>
   - JSON with the full article data for a section ("O tym się mówi",
     "Wybrane dla Ciebie", "Wiadomości", "Sport", "Biznes", ...).
3. Livebar iframe https://livebar.onet.pl/desktop/<uuid>
   - server-rendered HTML with time-stamped breaking-news items.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .models import Article

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HOME_URL = "https://www.onet.pl/"
FEED_API_URL = "https://mp-feed-api.onet.pl/2.0/feeds/{uuid}"

LIVEBAR_URL_RE = re.compile(r"https://livebar\.onet\.pl/desktop/[0-9a-fA-F-]{36}")
FEED_UUID_RE = re.compile(r'"feedUuid"\s*:\s*"([0-9a-fA-F-]{36})"')

TRACKING_PARAMS = {"utm_source", "utm_campaign", "utm_medium", "utm_term", "utm_content"}

DOMAIN_CATEGORIES = {
    "przegladsportowy.onet.pl": "sport",
    "sport.onet.pl": "sport",
    "twojsport.onet.pl": "sport",
    "businessinsider.com.pl": "biznes",
    "biznes.onet.pl": "biznes",
    "kobieta.onet.pl": "lifestyle",
    "kultura.onet.pl": "kultura",
    "podroze.onet.pl": "podróże",
    "auto-swiat.pl": "motoryzacja",
    "komputerswiat.pl": "technologia",
    "medonet.pl": "zdrowie",
    "fakt.pl": "wydarzenia",
    "mobile.onet.pl": "mobile",
    "pogoda.onet.pl": "pogoda",
    "dom.wprost.pl": "dom i ogród",
}

PATH_CATEGORIES = {
    "kraj": "kraj",
    "swiat": "świat",
    "sport": "sport",
    "biznes": "biznes",
    "kultura": "kultura",
    "podroze": "podróże",
    "pieniadze": "finanse",
    "finanse": "finanse",
    "wydarzenia": "wydarzenia",
    "prawo": "prawo",
    "telewizja": "kultura",
    "gaming": "gry",
    "pilka-nozna": "sport",
    "zdrowa-dieta": "zdrowie",
    "lepsze-zdrowie-dluzsze-zycie": "zdrowie",
}

SKIP_TITLE_MARKERS = ("[reklama]", "materiał promocyjny", "materiał promowany")


@dataclass
class Feed:
    uuid: str
    title: str
    articles: list = field(default_factory=list)


def clean_url(url: str) -> str:
    """Strip tracking (utm_*) query parameters from a URL."""
    if not url:
        return url
    try:
        parts = urlparse(url)
        pairs = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS
        ]
        return urlunparse(
            (parts.scheme, parts.netloc, parts.path, parts.params, urlencode(pairs), "")
        )
    except ValueError:
        return url


def livebar_sort_minutes(hhmm: str, now: datetime, offset_hours: int) -> Optional[float]:
    """Approximate minutes elapsed since an 'HH:MM' shown in PL local time.

    The livebar only shows a clock (no date), so the local offset is
    approximated from the current month (CEST = +2, CET = +1).
    """
    match = re.match(r"^(\d{1,2}):(\d{2})$", hhmm or "")
    if not match:
        return None
    local_min = int(match.group(1)) * 60 + int(match.group(2))
    utc_min = local_min - offset_hours * 60
    delta = (now.hour * 60 + now.minute - utc_min) % 1440
    return float(delta)


def category_from_url(url: str) -> Optional[str]:
    """Derive a human-readable category from an article URL."""
    if not url:
        return None
    try:
        parts = urlparse(url)
    except ValueError:
        return None
    host = (parts.netloc or "").lower().removeprefix("www.")
    segments = [s for s in (parts.path or "").split("/") if s]

    if host in DOMAIN_CATEGORIES:
        return DOMAIN_CATEGORIES[host]
    if host == "onet.pl":
        # cross-site form: /informacje/<source>/<slug>/<id>
        if segments and segments[0] == "informacje" and len(segments) >= 2:
            return segments[1]
        if segments:
            return PATH_CATEGORIES.get(segments[0], segments[0])
        return None
    if host.endswith(".onet.pl"):
        if segments:
            return PATH_CATEGORIES.get(segments[0], segments[0])
        section = host.split(".")[0]
        return PATH_CATEGORIES.get(section, section)
    if segments:
        return PATH_CATEGORIES.get(segments[0], segments[0])
    return host or None


class OnetScraper:
    """Fetches, cleans and ranks Onet.pl news."""

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

    # ------------------------------------------------------------------
    # low-level HTTP
    # ------------------------------------------------------------------
    def _get_bytes(self, url: str) -> bytes:
        resp = self.session.get(url, timeout=self.settings.timeout)
        resp.raise_for_status()
        return resp.content

    def _get_text(self, url: str) -> str:
        return self._get_bytes(url).decode("utf-8", errors="replace")

    def _get_json(self, url: str):
        return json.loads(self._get_text(url))

    # ------------------------------------------------------------------
    # discovery (homepage)
    # ------------------------------------------------------------------
    @staticmethod
    def extract_livebar_url(home_html: str) -> Optional[str]:
        match = LIVEBAR_URL_RE.search(home_html)
        return match.group(0) if match else None

    @staticmethod
    def extract_feed_uuids(home_html: str) -> list:
        """Distinct feed UUIDs in the order they appear in the page."""
        seen = set()
        out = []
        for match in FEED_UUID_RE.finditer(home_html):
            uuid = match.group(1)
            if uuid not in seen:
                seen.add(uuid)
                out.append(uuid)
        return out

    # ------------------------------------------------------------------
    # feed API
    # ------------------------------------------------------------------
    def _fetch_feed(self, uuid: str) -> Feed:
        data = self._get_json(FEED_API_URL.format(uuid=uuid))
        title = (data.get("title") or "").strip() or f"Feed {uuid[:8]}"
        entries = data.get("entries") or []
        feed = Feed(uuid=uuid, title=title)
        for entry in entries:
            article = self._entry_to_article(entry, title, uuid)
            if article is not None:
                feed.articles.append(article)
        return feed

    @staticmethod
    def _entry_to_article(entry: dict, section: str, feed_uuid: str) -> Optional[Article]:
        if not isinstance(entry, dict):
            return None
        title = ((entry.get("title") or {}).get("text") or "").strip()
        link = (entry.get("link") or {}).get("href") or ""
        if not title or not link.startswith("http"):
            return None
        # author profile pages and promo material are not articles
        if "/autorzy/" in link:
            return None
        low_title = title.lower()
        if any(marker in low_title for marker in SKIP_TITLE_MARKERS):
            return None
        link = clean_url(link)

        image = None
        image_obj = entry.get("image")
        if isinstance(image_obj, dict):
            image = image_obj.get("url") or None

        summary = None
        summary_obj = entry.get("summary")
        if isinstance(summary_obj, dict):
            summary = summary_obj.get("text") or None

        source = None
        sources = entry.get("sources")
        if isinstance(sources, list) and sources and isinstance(sources[0], dict):
            source = sources[0].get("name") or None

        authors = []
        for author in entry.get("authors") or []:
            if isinstance(author, dict) and author.get("name"):
                authors.append(author["name"])

        reactions = 0
        for emotion in entry.get("emotions") or []:
            if isinstance(emotion, dict):
                try:
                    reactions += int(emotion.get("value") or 0)
                except (TypeError, ValueError):
                    pass

        hardness = entry.get("hardness")
        try:
            hardness = float(hardness) if hardness is not None else None
        except (TypeError, ValueError):
            hardness = None

        kind = (entry.get("type") or {}).get("code") or "article"

        return Article(
            title=title,
            url=link,
            image=image,
            source=source,
            section=section,
            category=category_from_url(link),
            kind=kind,
            is_premium=bool(entry.get("isPremium")) or entry.get("content-type") == "premium",
            summary=summary,
            authors=authors,
            reading_time=entry.get("readingTime") or None,
            hardness=hardness,
            reactions=reactions,
            feed_uuid=feed_uuid,
        )

    # ------------------------------------------------------------------
    # livebar (breaking news)
    # ------------------------------------------------------------------
    def _fetch_livebar(self, iframe_url: str) -> list:
        page = self._get_text(iframe_url)
        soup = BeautifulSoup(page, "html.parser")
        container = soup.select_one("div[data-section='livebar']") or soup
        now = datetime.now(timezone.utc)
        # the livebar clock is PL local time: CEST (Mar-Oct) = UTC+2, else CET
        offset_hours = 2 if now.month in (3, 4, 5, 6, 7, 8, 9, 10) else 1
        items = []
        seen = set()
        for anchor in container.select("a.item"):
            href = anchor.get("href") or ""
            if not href.startswith("http"):
                continue
            href = clean_url(href)
            if href in seen:
                # the marquee duplicates items in an aria-hidden group
                continue
            seen.add(href)

            time_el = anchor.select_one("span.time")
            published = time_el.get_text(strip=True) if time_el else None

            full_text = anchor.get_text(" ", strip=True)
            title = full_text
            if published and full_text.startswith(published):
                title = full_text[len(published):].strip(" \t:|–-")
            if not title:
                continue
            item = Article(
                title=title,
                url=href,
                section="Na żywo (pilne)",
                category=category_from_url(href),
                kind="live",
                breaking=True,
                published=published,
            )
            # sortable key for the cross-source merge (minutes since "now")
            item._sort_min = livebar_sort_minutes(published, now, offset_hours)
            items.append(item)
        return items

    # ------------------------------------------------------------------
    # ranking / merging
    # ------------------------------------------------------------------
    # feed titles that mark the "most popular today" ranking on onet.pl
    MAIN_FEED_MARKERS = (
        "o tym się mówi",
        "najpopularniejsze",
        "najciekawsze",
        "najgorętsze",
    )

    @staticmethod
    def _score(article: Article, feed_index: int) -> float:
        score = 0.0
        if article.breaking:
            score += 1000.0
        if article.hardness:
            score += article.hardness * 20.0
        score += min(article.reactions, 3000) / 30.0
        # position in the feed is Onet's own popularity ranking
        score += max(0.0, 40.0 - feed_index) * 2.0
        return score

    def _merge_rank(self, articles: list, breaking: list, main_uuid: Optional[str]) -> list:
        merged: dict = {}
        order: list = []

        def upsert(article: Article, feed_index: int) -> None:
            article.score = self._score(article, feed_index)
            key = article.url
            if key in merged:
                existing = merged[key]
                if article.breaking:
                    existing.breaking = True
                    if not existing.published and article.published:
                        existing.published = article.published
                    existing.score = max(existing.score, article.score)
                elif article.score > existing.score:
                    existing.score = article.score
                return
            merged[key] = article
            order.append(key)

        for index, article in enumerate(breaking):
            upsert(article, 0)
        for index, article in enumerate(articles):
            # the main ("najpopularniejsze") feed keeps its served order
            feed_index = index if article.feed_uuid == main_uuid else index + 100
            upsert(article, feed_index)

        ranked = [merged[key] for key in sorted(order, key=lambda k: -merged[k].score)]
        return ranked[: self.settings.max_articles]

    # ------------------------------------------------------------------
    # orchestration
    # ------------------------------------------------------------------
    def scrape(self) -> dict:
        scraped_at = datetime.now(timezone.utc).isoformat()
        errors: list = []
        all_articles: list = []
        feeds: list = []
        popular: list = []
        livebar_url = None
        main_feed = None

        log.info("scrape: fetching homepage")
        home = self._get_text(HOME_URL)
        livebar_url = self.extract_livebar_url(home)

        if self.settings.feed_uuids:
            uuids = self.settings.feed_uuids
        else:
            uuids = self.extract_feed_uuids(home)[: self.settings.max_feeds]
        log.info("scrape: %d feeds to fetch, livebar=%s", len(uuids), livebar_url)

        main_uuid = None
        best_count = -1
        for uuid in uuids:
            try:
                feed = self._fetch_feed(uuid)
            except Exception as exc:  # noqa: BLE001 - one bad feed must not kill the scrape
                log.warning("scrape: feed %s failed: %s", uuid, exc)
                errors.append(f"feed {uuid}: {exc}")
                continue
            feeds.append({"uuid": uuid, "title": feed.title, "count": len(feed.articles)})
            all_articles.extend(feed.articles)
            title_l = feed.title.lower()
            if any(marker in title_l for marker in self.MAIN_FEED_MARKERS):
                # the "most popular" feed wins by name, whatever its size
                if main_uuid is None:
                    main_uuid = uuid
                    popular = list(feed.articles)
            elif len(feed.articles) > best_count:
                best_count = len(feed.articles)
                if main_uuid is None:
                    main_uuid = uuid
                    popular = list(feed.articles)

        if main_uuid is not None:
            main_feed = next((f for f in feeds if f["uuid"] == main_uuid), None)
            log.info(
                "scrape: main feed = %r (%d articles)",
                main_feed["title"],
                main_feed["count"],
            )

        breaking: list = []
        if livebar_url:
            try:
                breaking = self._fetch_livebar(livebar_url)
                log.info("scrape: livebar items: %d", len(breaking))
            except Exception as exc:  # noqa: BLE001
                log.warning("scrape: livebar failed: %s", exc)
                errors.append(f"livebar: {exc}")
        else:
            errors.append("livebar: iframe URL not found in homepage")

        articles = self._merge_rank(all_articles, breaking, main_uuid)

        # Article objects (not dicts): the aggregator merges sources and does
        # the final to_dict() conversion.
        return {
            "scraped_at": scraped_at,
            "livebar_url": livebar_url,
            "main_feed": main_feed,
            "feeds": feeds,
            "articles": articles,
            "popular": popular,
            "breaking": breaking,
            "errors": errors,
        }
