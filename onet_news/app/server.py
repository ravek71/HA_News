"""Flask REST API + small HTML status page."""
from __future__ import annotations

import html
import logging
import threading
from typing import Callable, Optional

from flask import Flask, jsonify, request

from .store import Store

log = logging.getLogger(__name__)

PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Onet News — HA News</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         margin: 0; padding: 1rem; line-height: 1.45; }
  h1 { font-size: 1.25rem; margin: 0 0 .25rem; }
  .meta { opacity: .75; font-size: .85rem; margin-bottom: 1rem; }
  .status { display: inline-block; padding: .1rem .5rem; border-radius: 1rem;
            font-size: .8rem; font-weight: 600; }
  .ok { background: #2e7d32; color: #fff; }
  .degraded { background: #ef6c00; color: #fff; }
  .waiting { background: #757575; color: #fff; }
  section { margin-bottom: 1.5rem; }
  h2 { font-size: 1rem; margin: 0 0 .5rem; border-bottom: 1px solid #8884;
       padding-bottom: .25rem; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { margin: 0 0 .65rem; }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .time { font-variant-numeric: tabular-nums; opacity: .7; margin-right: .4rem; }
  .tag { font-size: .7rem; padding: .05rem .4rem; border-radius: .4rem;
         background: #f44336; color: #fff; margin-left: .4rem; vertical-align: middle; }
  .tag.premium { background: #6a1b9a; }
  .cat { opacity: .55; font-size: .75rem; margin-left: .4rem; }
  .empty { opacity: .6; font-style: italic; }
  .err { color: #c62828; font-size: .85rem; word-break: break-word; }
  .links { font-size: .8rem; opacity: .8; }
  .links code { background: #8882; padding: .05rem .3rem; border-radius: .3rem; }
</style>
</head>
<body>
  <h1>Onet News</h1>
  <div class="meta">
    <span class="status @@STATUS_CLASS@@">@@STATUS@@</span>
    &nbsp;ostatnie odświeżenie: @@SCRAPED_AT@@
  </div>
  @@ERRORS@@

  <section>
    <h2>Najnowsze (ranking) — @@ARTICLES_COUNT@@</h2>
    @@ARTICLES@@
  </section>

  <section>
    <h2>Na żywo (pilne) — @@BREAKING_COUNT@@</h2>
    @@BREAKING@@
  </section>

  <section>
    <h2>Feedy</h2>
    @@FEEDS@@
  </section>

  <section class="links">
    API: <code>/api/articles</code> <code>/api/popular</code>
    <code>/api/breaking</code> <code>/api/feeds</code>
    <code>/api/status</code> <code>/api/refresh</code> (POST)
  </section>
</body>
</html>
"""


def _esc(value) -> str:
    return html.escape(str(value), quote=True) if value is not None else ""


def _article_li(article: dict, show_time: bool = True) -> str:
    title = _esc(article.get("title"))
    url = _esc(article.get("url"))
    parts = [f'<li><a href="{url}" target="_blank" rel="noopener">{title}']
    if article.get("is_premium"):
        parts.append('<span class="tag premium">premium</span>')
    if article.get("breaking"):
        parts.append('<span class="tag">pilne</span>')
    parts.append("</a>")
    if show_time and article.get("published"):
        parts.append(f'<div class="time">{_esc(article["published"])}</div>')
    if article.get("category"):
        parts.append(f'<span class="cat">{_esc(article["category"])}</span>')
    parts.append("</li>")
    return "".join(parts)


def render_page(snap: dict) -> str:
    status = snap.get("status") or "waiting"
    status_class = {"ok": "ok", "degraded": "degraded"}.get(status, "waiting")

    articles = snap.get("articles") or []
    articles_html = (
        "<ul>" + "".join(_article_li(a) for a in articles[:40]) + "</ul>"
        if articles
        else '<p class="empty">Brak danych — pierwsze odświeżenie w toku.</p>'
    )

    breaking = snap.get("breaking") or []
    breaking_html = (
        "<ul>" + "".join(_article_li(a) for a in breaking) + "</ul>"
        if breaking
        else '<p class="empty">Brak wiadomości pilnych.</p>'
    )

    feeds = snap.get("feeds") or []
    feeds_html = (
        "<ul>"
        + "".join(
            f'<li><strong>{_esc(f.get("title"))}</strong> '
            f'<span class="cat">{f.get("count")} artykułów</span></li>'
            for f in feeds
        )
        + "</ul>"
        if feeds
        else '<p class="empty">Brak danych.</p>'
    )

    errors = snap.get("errors") or []
    errors_html = (
        '<section><div class="err">Ostatni błąd: '
        + "<br>".join(_esc(e) for e in errors)
        + "</div></section>"
        if errors
        else ""
    )

    scraped_at = snap.get("scraped_at") or "—"
    page = PAGE
    page = page.replace("@@STATUS_CLASS@@", status_class)
    page = page.replace("@@STATUS@@", _esc(status))
    page = page.replace("@@SCRAPED_AT@@", _esc(scraped_at))
    page = page.replace("@@ERRORS@@", errors_html)
    page = page.replace("@@ARTICLES_COUNT@@", str(len(articles)))
    page = page.replace("@@ARTICLES@@", articles_html)
    page = page.replace("@@BREAKING_COUNT@@", str(len(breaking)))
    page = page.replace("@@BREAKING@@", breaking_html)
    page = page.replace("@@FEEDS@@", feeds_html)
    return page


def make_app(store: Store, on_refresh: Optional[Callable[[], None]] = None) -> Flask:
    app = Flask(__name__)

    @app.after_request
    def add_cors(response):
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
        return response

    @app.get("/")
    def index():
        return render_page(store.snapshot()), 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/api/endpoints")
    def api_endpoints():
        return jsonify(
            name="HA News - Onet.pl scraper",
            endpoints=[
                "GET /api/articles?limit=60&include_breaking=1",
                "GET /api/popular?limit=30",
                "GET /api/breaking",
                "GET /api/feeds",
                "GET /api/status",
                "POST /api/refresh",
                "GET /healthz",
            ],
        )

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/api/status")
    def api_status():
        return jsonify(store.snapshot())

    @app.get("/api/articles")
    def api_articles():
        snap = store.snapshot()
        limit = _limit(request.args.get("limit", default=60, type=int), 60)
        include_breaking = request.args.get("include_breaking", default="1") not in (
            "0",
            "false",
            "no",
        )
        articles = snap["articles"]
        if not include_breaking:
            articles = [a for a in articles if not a.get("breaking")]
        return jsonify(count=len(articles[:limit]), articles=articles[:limit])

    @app.get("/api/popular")
    def api_popular():
        snap = store.snapshot()
        limit = _limit(request.args.get("limit", default=30, type=int), 30)
        return jsonify(
            count=len(snap["popular"][:limit]),
            main_feed=snap["main_feed"],
            articles=snap["popular"][:limit],
        )

    @app.get("/api/breaking")
    def api_breaking():
        snap = store.snapshot()
        return jsonify(
            count=len(snap["breaking"]),
            livebar_url=snap["livebar_url"],
            articles=snap["breaking"],
        )

    @app.get("/api/feeds")
    def api_feeds():
        snap = store.snapshot()
        return jsonify(feeds=snap["feeds"])

    @app.post("/api/refresh")
    def api_refresh():
        if on_refresh is None:
            return jsonify(ok=False, error="refresh unavailable"), 503
        threading.Thread(target=on_refresh, name="manual-scrape", daemon=True).start()
        return jsonify(ok=True, message="scrape started in background")

    return app
