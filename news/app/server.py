"""Flask REST API + small HTML status page."""
from __future__ import annotations

import html
import logging
import threading
from typing import Callable, Optional

from flask import Flask, jsonify, request

from .store import STALE_AFTER_MINUTES, Store

log = logging.getLogger(__name__)

PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HA News — Onet i WP</title>
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
  .warn { color: #ef6c00; font-size: .85rem; font-weight: 600; margin-bottom: 1rem; }
  @media (prefers-color-scheme: dark) { .warn { color: #ffb74d; } }
  .err { color: #c62828; font-size: .85rem; word-break: break-word; }
  .links { font-size: .8rem; opacity: .8; }
  .links code { background: #8882; padding: .05rem .3rem; border-radius: .3rem; }
</style>
</head>
<body>
  <h1>Onet News</h1>
  <div class="meta">
    <span class="status @@STATUS_CLASS@@">@@STATUS@@</span>
    &nbsp;@@AGE@@
  </div>
  @@STALE@@
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
    <h2>Feedy (Onet)</h2>
    @@FEEDS@@
  </section>

  <section>
    <h2>Źródła</h2>
    @@SOURCES@@
  </section>

  <section class="links">
    API: <code>/api/articles</code> <code>/api/popular</code>
    <code>/api/breaking</code> <code>/api/feeds</code>
    <code>/api/status</code> <code>/api/refresh</code> (POST)
  </section>
</body>
</html>
"""

BREAKING_PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pilne — Onet i WP</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         margin: 0; padding: 1rem; line-height: 1.45; background: transparent; }
  header { display: flex; align-items: center; gap: .5rem; margin-bottom: .75rem; }
  .dot { width: .6rem; height: .6rem; border-radius: 50%; background: #f44336;
         box-shadow: 0 0 0 0 #f44336; animation: pulse 2s infinite; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 #f4433680; }
    70% { box-shadow: 0 0 0 .5rem #f4433600; }
    100% { box-shadow: 0 0 0 0 #f4433600; }
  }
  .meta { opacity: .7; font-size: .8rem; }
  .meta.stale { color: #ef6c00; font-weight: 600; opacity: 1; }
  @media (prefers-color-scheme: dark) { .meta.stale { color: #ffb74d; } }
  ul { list-style: none; padding: 0; margin: 0; }
  li { margin: 0 0 .8rem; padding-left: .9rem; position: relative; }
  li::before { content: ""; position: absolute; left: 0; top: .5rem;
               width: .35rem; height: .35rem; border-radius: 50%; background: #f44336; }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .time { font-variant-numeric: tabular-nums; opacity: .7; margin-right: .4rem; }
  .cat { opacity: .55; font-size: .72rem; margin-left: .4rem; }
  .tag { font-size: .68rem; padding: .05rem .4rem; border-radius: .8rem; margin-left: .35rem;
         border: 1px solid #8884; opacity: .8; vertical-align: middle; }
  .tag.premium { border-color: #c9a227; color: #c9a227; opacity: 1; }
  .empty { opacity: .65; font-style: italic; margin: 2rem 0; text-align: center; }
  .filters { display: flex; gap: .5rem; align-items: center; margin: .4rem 0 .7rem; flex-wrap: wrap; }
  #q { flex: 1 1 14rem; min-width: 10rem; padding: .35rem .6rem; font-size: .85rem;
       border: 1px solid #8884; border-radius: .5rem; background: #8881; color: inherit; }
  #q:focus { outline: none; border-color: #f44336; }
  .chips { display: flex; gap: .3rem; flex-wrap: wrap; }
  .chip { padding: .25rem .6rem; font-size: .78rem; border-radius: 1rem; cursor: pointer;
          border: 1px solid #8884; background: transparent; color: inherit; }
  .chip.active { background: #f44336; border-color: #f44336; color: #fff; }
  .chip .n { opacity: .65; font-size: .72rem; margin-left: .2rem; }
</style>
</head>
<body>
  <header>
    <span class="dot"></span>
    <span class="meta @@STAMP_CLASS@@" id="stamp">@@STAMP@@</span>
  </header>
  <div class="filters">
    <input id="q" type="search" placeholder="Szukaj w tytułach…" autocomplete="off">
    <div class="chips" id="chips"></div>
  </div>
  <ul id="list">
@@BODY@@
  </ul>
  <p class="empty" id="empty" style="display:@@EMPTY_STYLE@@">Brak wiadomości pilnych.</p>
<script>
(function () {
  var list = document.getElementById('list');
  var chips = document.getElementById('chips');
  var q = document.getElementById('q');
  var empty = document.getElementById('empty');
  var stamp = document.getElementById('stamp');
  var activeCat = '';
  var term = '';

  function norm(s) {
    return s.toLowerCase()
      .replace(/ą/g, 'a').replace(/ć/g, 'c').replace(/ę/g, 'e')
      .replace(/ł/g, 'l').replace(/ń/g, 'n').replace(/ó/g, 'o')
      .replace(/ś/g, 's').replace(/ź/g, 'z').replace(/ż/g, 'z');
  }
  function lis() { return Array.prototype.slice.call(list.children); }
  function catOf(li) {
    var c = li.querySelector('.cat');
    return c ? c.textContent.trim() : '';
  }
  function titleOf(li) {
    var a = li.querySelector('a');
    return a ? a.textContent.trim() : '';
  }

  function renderChips() {
    var counts = {};
    lis().forEach(function (li) {
      var c = catOf(li);
      if (c) counts[c] = (counts[c] || 0) + 1;
    });
    chips.textContent = '';
    function chip(label, cat, count) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip' + (activeCat === cat ? ' active' : '');
      b.textContent = label;
      if (count != null) {
        var n = document.createElement('span');
        n.className = 'n';
        n.textContent = count;
        b.appendChild(n);
      }
      b.addEventListener('click', function () {
        activeCat = (activeCat === cat) ? '' : cat;
        renderChips();
        apply();
      });
      chips.appendChild(b);
    }
    chip('Wszystkie', '', null);
    Object.keys(counts).sort().forEach(function (c) { chip(c, c, counts[c]); });
  }

  function apply() {
    var shown = 0;
    var total = lis().length;
    lis().forEach(function (li) {
      var ok = (activeCat === '' || catOf(li) === activeCat) &&
               (term === '' || norm(titleOf(li)).indexOf(term) !== -1);
      li.style.display = ok ? '' : 'none';
      if (ok) shown++;
    });
    empty.style.display = shown === 0 ? '' : 'none';
    empty.textContent = total === 0
      ? 'Brak wiadomości pilnych.'
      : 'Brak wyników dla wybranego filtra.';
  }

  q.addEventListener('input', function () {
    term = norm(q.value.trim());
    apply();
  });

  function load() {
    fetch(location.pathname, { headers: { 'Accept': 'text/html' } })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (text) {
        if (!text) return;
        var doc = new DOMParser().parseFromString(text, 'text/html');
        var nl = doc.getElementById('list');
        if (!nl) return;
        while (list.firstChild) list.removeChild(list.firstChild);
        while (nl.firstChild) list.appendChild(nl.firstChild);
        var ns = doc.getElementById('stamp');
        if (ns) {
          stamp.textContent = ns.textContent;
          stamp.className = ns.className;
        }
        renderChips();
        apply();
      })
      .catch(function () {});
  }
  setInterval(load, 60000);
  renderChips();
  apply();
})();
</script>
</body>
</html>
"""


def _esc(value) -> str:
    return html.escape(str(value), quote=True) if value is not None else ""


def _limit(value: Optional[int], default: int, max_value: int = 500) -> int:
    """Clamp a ?limit= query param to 1..max_value (default when missing)."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, max_value))


def _age_pl(minutes: int) -> str:
    """Compact Polish relative age: '10 min temu', '1 godz. 5 min temu'."""
    if minutes < 1:
        return "przed chwilą"
    if minutes < 60:
        return f"{minutes} min temu"
    hours, rem = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} godz. {rem} min temu" if rem else f"{hours} godz. temu"
    days, rem_hours = divmod(hours, 24)
    label = "1 dzień" if days == 1 else f"{days} dni"
    return f"{label} i {rem_hours} godz. temu" if rem_hours else f"{label} temu"


def _update_line(snap: dict) -> str:
    """'ostatnia aktualizacja: 10 min temu' for the page meta lines."""
    age = snap.get("age_minutes")
    if age is None:
        return "brak danych (pierwsze odświeżenie w toku)"
    return f"ostatnia aktualizacja: {_age_pl(age)}"


def _article_li(article: dict, show_time: bool = True, show_breaking_tag: bool = True) -> str:
    title = _esc(article.get("title"))
    url = _esc(article.get("url"))
    parts = [f'<li><a href="{url}" target="_blank" rel="noopener">{title}']
    site = article.get("site")
    if site == "wp":
        parts.append('<span class="tag">WP</span>')
    elif site == "onet":
        parts.append('<span class="tag">Onet</span>')
    if article.get("is_premium"):
        parts.append('<span class="tag premium">premium</span>')
    if show_breaking_tag and article.get("breaking"):
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

    def _source_line(name: str, info: dict) -> str:
        label = {"onet": "Onet", "wp": "WP"}.get(name, name)
        if not info.get("enabled"):
            detail, err = "wyłączone w opcjach", ""
        elif info.get("ok"):
            detail, err = (
                f"ok — {info.get('articles', 0)} artykułów, "
                f"{info.get('breaking', 0)} pilnych",
                "",
            )
        else:
            detail, err = "błąd pobierania", _esc(info.get("error"))
        err_html = f' <span class="err">({err})</span>' if err else ""
        return f'<li><strong>{label}</strong> <span class="cat">{detail}</span>{err_html}</li>'

    sources = snap.get("sources") or {}
    sources_html = (
        "<ul>" + "".join(_source_line(n, s) for n, s in sources.items()) + "</ul>"
        if sources
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

    update_line = _update_line(snap)
    stale = bool(snap.get("stale"))
    stale_html = (
        '<div class="warn">⚠ Problem z pobieraniem danych — ostatnia '
        f"aktualizacja jest starsza niż {STALE_AFTER_MINUTES} min</div>"
        if stale
        else ""
    )

    page = PAGE
    page = page.replace("@@STATUS_CLASS@@", status_class)
    page = page.replace("@@STATUS@@", _esc(status))
    page = page.replace("@@AGE@@", _esc(update_line))
    page = page.replace("@@STALE@@", stale_html)
    page = page.replace("@@ERRORS@@", errors_html)
    page = page.replace("@@ARTICLES_COUNT@@", str(len(articles)))
    page = page.replace("@@ARTICLES@@", articles_html)
    page = page.replace("@@BREAKING_COUNT@@", str(len(breaking)))
    page = page.replace("@@BREAKING@@", breaking_html)
    page = page.replace("@@FEEDS@@", feeds_html)
    page = page.replace("@@SOURCES@@", sources_html)
    return page


def render_breaking(snap: dict) -> str:
    breaking = snap.get("breaking") or []
    # on this page every item is breaking, so the "pilne" tag is redundant
    items = "".join(_article_li(a, show_breaking_tag=False) for a in breaking)
    update_line = _update_line(snap)
    stale = bool(snap.get("stale"))
    stamp = f"⚠ problem z pobieraniem danych — {update_line}" if stale else update_line
    page = BREAKING_PAGE
    page = page.replace("@@STAMP@@", _esc(stamp))
    page = page.replace("@@STAMP_CLASS@@", "stale " if stale else "")
    page = page.replace("@@BODY@@", items)
    page = page.replace("@@EMPTY_STYLE@@", "" if not breaking else "none")
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

    @app.get("/breaking")
    def breaking():
        return render_breaking(store.snapshot()), 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/api/endpoints")
    def api_endpoints():
        return jsonify(
            name="HA News - Onet.pl i WP.pl scraper",
            endpoints=[
                "GET /api/articles?limit=60&include_breaking=1",
                "GET /api/popular?limit=30",
                "GET /api/breaking",
                "GET /api/feeds",
                "GET /api/status",
                "POST /api/refresh",
                "GET /breaking  (strona HTML - tylko pilne, auto-refresh)",
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
