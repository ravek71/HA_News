# Onet News — API documentation

Base URL: `http://<host>:8080`

All responses are `application/json` (UTF-8, `ensure_ascii=False`).
CORS is enabled (`Access-Control-Allow-Origin: *`).

The app scrapes two sources, each toggleable in the app options
(`enable_onet` / `enable_wp`, both on by default):

* **Onet.pl** — feed API (`mp-feed-api.onet.pl`, „O tym się mówi" ranking)
  + livebar (breaking news),
* **WP.pl** — the main stream on the `www.wp.pl` homepage (server-side
  rendered teasers) + the „Najnowsze" timeline on `wiadomosci.wp.pl`
  (breaking news, with publication timestamps).

Every article in the API responses has a `site` field (`"onet"` or `"wp"`).

## `GET /healthz`

Liveness probe (used by the HA watchdog).

```json
{"status": "ok"}
```

## `GET /api/status`

Scrape status.

```json
{
  "status": "ok",
  "scraped_at": "2026-11-18T09:30:00+00:00",
  "age_minutes": 10,
  "stale": false,
  "last_attempt": "2026-11-18T09:30:05+00:00",
  "last_error": null,
  "sources": {
    "onet": {"enabled": true, "ok": true, "error": null, "articles": 60, "breaking": 10},
    "wp":   {"enabled": true, "ok": true, "error": null, "articles": 111, "breaking": 35}
  },
  "all_ok": true,
  "livebar_url": "https://livebar.onet.pl/desktop/02a91f84-...",
  "main_feed": {"uuid": "8175f6e3-...", "title": "O tym się mówi", "count": 30},
  "feeds": [{"uuid": "...", "title": "...", "count": 30}],
  "errors": []
}
```

`status`: `waiting` (before first scrape), `ok`, `degraded` (last scrape
failed — or one of the enabled sources failed — stale data served).

`sources`: per-source status for every known source (enabled or not):
`enabled` (from app options), `ok` (`null` when disabled), `error`
(message when the source failed), `articles` / `breaking` (counts from the
last successful scrape of that source). `all_ok` is `true` when every
enabled source succeeded.

`age_minutes`: whole minutes since the last **successful** update
(`null` before the first scrape). The HTML pages display it as a relative
time („ostatnia aktualizacja: 10 min temu").

`stale`: `true` when the last successful update is older than **30 min**
(`STALE_AFTER_MINUTES`). Use it to build a notification automation; the UI
shows an orange „problem with data fetching" warning in the same case.

## `GET /api/articles?limit=60&include_breaking=1`

Merged ranking of all enabled sources, interleaved (onet #1, wp #1,
onet #2, wp #2, …). Breaking items are excluded (they have the dedicated
`/api/breaking` list). `limit` (1–500, default 60).
`include_breaking` (`0`/`1`, default `1`).

```json
{
  "count": 12,
  "articles": [ { "title": "...", "url": "...", "...": "..." } ]
}
```

## `GET /api/popular?limit=30`

The main feed („O tym się mówi" — Onet's own *most popular today* ranking)
in the order served by Onet.

```json
{
  "count": 30,
  "main_feed": {"uuid": "...", "title": "O tym się mówi", "count": 30},
  "articles": [ ... ]
}
```

## `GET /api/breaking`

Merged breaking-news list from all enabled sources — Onet's livebar plus
WP.pl's „Najnowsze" timeline — sorted by publication time, newest first,
with each item's `site` label.

```json
{
  "count": 45,
  "livebar_url": "https://livebar.onet.pl/desktop/...",
  "articles": [
    {
      "title": "Rozpoczęło się posiedzenie koalicji chętnych w Berlinie. …",
      "url": "https://wiadomosci.onet.pl/swiat/.../2l65q3w",
      "site": "onet",
      "section": "Na żywo (pilne)",
      "category": "świat",
      "kind": "live",
      "published": "14:39",
      "breaking": true
    },
    {
      "title": "Ostatnie cieplejsze dni? Na mapach widać duże ochłodzenie",
      "url": "https://pogoda.wp.pl/ostatnie-cieplejsze-dni-...a",
      "site": "wp",
      "section": "Najnowsze (pilne)",
      "category": "pogoda",
      "kind": "live",
      "published": "19 min",
      "breaking": true
    }
  ]
}
```

## `GET /api/feeds`

Feeds discovered on the onet.pl homepage.

```json
{"feeds": [{"uuid": "...", "title": "O tym się mówi", "count": 30}]}
```

## `POST /api/refresh`

Triggers a scrape in the background.

```json
{"ok": true, "message": "scrape started in background"}
```

## `GET /breaking`

Standalone HTML page with only the breaking items (merged from Onet's
livebar and WP's „Najnowsze" timeline, newest first, each with a source
tag) — intended for embedding in a dashboard card. No article title
heading and no counter; the header shows a pulsing dot and the relative
last-update time
(„ostatnia aktualizacja: 10 min temu"), which turns orange with a
„problem with data fetching" notice when the data is older than 30 min.
Features: title search (Polish-diacritic-insensitive), category chips,
60 s auto-refresh preserving the active filters, light/dark theme.
Served with `X-Frame-Options: SAMEORIGIN` (same-origin embedding allowed).

## Article object

| Field | Type | Description |
|---|---|---|
| `title` | string | Article title |
| `url` | string | Canonical URL (tracking params removed) |
| `image` | string? | Teaser image URL |
| `site` | string | Scraping source: `"onet"` or `"wp"` (1.2.0+) |
| `source` | string? | Publisher name (Onet, Business Insider, …) |
| `section` | string? | Feed/section name („O tym się mówi", „Na żywo (pilne)", „Strumień główny", „Najnowsze (pilne)") |
| `category` | string? | Category derived from the URL (kraj, świat, sport, finanse, …) |
| `kind` | string | `article`, `big_story`, `commentary`, `in_short`, `live`, … |
| `is_premium` | bool | Whether the article is premium/paywalled |
| `summary` | string? | Teaser text |
| `authors` | list[string] | Author names |
| `reading_time` | ? | Reading time if provided by the feed |
| `hardness` | float? | Onet's internal importance score |
| `reactions` | int | Sum of reaction counters |
| `published` | string? | Publication time — Onet livebar: `HH:MM` (local); WP timeline: relative time as shown on the page (`19 min`) |
| `breaking` | bool | `true` for livebar / merged breaking items |
| `feed_uuid` | string? | UUID of the feed the article came from |
| `score` | float | Internal ranking score (see README) |
