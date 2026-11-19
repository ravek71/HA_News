# STATUS — stan projektu HA_News

Ostatnia aktualizacja: 2026-11-19 (wieczór)

## Stan: **1.1.0 działa w HA użytkownika** (na GitHubie, GHCR, zaktualizowana); **1.2.0 (WP.pl) gotowa na dysku** — testy lokalne zielone, do wgrania na GitHuba

## Co działa (zweryfikowane)

- **Repo GitHub** `ravek71/HA_News` — publiczne, main aktualny:
  - `server.py` zawiera stronę `/breaking` (BREAKING_PAGE, render_breaking,
    route, filtry JS, auto-refresh 60 s) — zweryfikowane z raw.githubusercontent.
  - `config.yaml` — wersja **1.0.2**.
- **CI (Actions)** — 2 ostatnie runy zielone (14:12 UTC); obraz **1.0.2** +
  `latest` wypchnięte do GHCR.
- **GHCR** `ravek71/onet-news` — **publiczny**, tagi: `1.0.0`, `1.0.2`, `latest`.
- **HA użytkownika** (`https://ha.bogura.duckdns.org`):
  - app **Onet News** zainstalowana (ID `b6f664cb_onet_news`),
  - ingress DZIAŁA, ale pod prefiksem **`/api/hassio_ingress/`** (nie
    `/api/ingress/` — stąd wcześniejsze 404; HA stoi za proxy OpenResty,
    anoniczny zewnętrzny dostęp do ingressu zwraca 401 — normalne, wymaga sesji),
  - token ingress: `v56jESc-TGu2ZJDq7WLdg_MFzCUfrCIQ-sgSo1gZuEo`
    (zweryfikowany przez użytkownika: `.../api/hassio_ingress/<token>/` → 200).

## Karta „Pilne" na dashboardzie (ROZWIĄZANIE: cookies-iframe-card)

`type: webview` **nie istnieje w core HA** (błąd "Unknown type encountered:
webview") — to karta custom. Wybrana karta: **cookies-iframe-card**
(`louisslee/cookies-iframe-card`, 1 plik JS 3.7 KB, HACS frontend albo ręcznie
do `www/` + zasób `/local/cookies-iframe-card.js`).

Dlaczego akurat ta:
- sama tworzy i **co 10 min odświeża** ciasteczko `ingress_session` (WS
  `supervisor/api` → POST `/ingress/session`), path `/api/hassio_ingress/` —
  dokładnie prefiks HA użytkownika → iframe bez 401,
- iframe same-origin (duckdns+HTTPS) → brak mixed content; nagłówek
  `X-Frame-Options: SAMEORIGIN` (sprawdzony) nie blokuje,
- sandbox z `allow-scripts` → auto-refresh 60 s i filtry z `/breaking` działają,
- `aspect_ratio` to procent szerokości (56% ≈ 16:9), ma edytor graficzny.
- ZALEŻNOŚĆ: import lit-element z `unpkg.com` (przeglądarka użytkownika musi
  mieć internet — ma, bo HA dostępny tylko zdalnie przez duckdns).

Adres działający:
```
https://ha.bogura.duckdns.org/api/hassio_ingress/v56jESc-TGu2ZJDq7WLdg_MFzCUfrCIQ-sgSo1gZuEo/breaking
```

Karta (YAML):
```yaml
type: custom:cookies-iframe-card
title: Pilne — Onet
url: https://ha.bogura.duckdns.org/api/hassio_ingress/v56jESc-TGu2ZJDq7WLdg_MFzCUfrCIQ-sgSo1gZuEo/breaking
aspect_ratio: 56%
```

Kopia pliku JS: `C:\Users\Rafal\AppData\Local\Temp\opencode\cookies-iframe-card.js`

## WERSJA 1.1.0 (sesja 2026-11-19 — na dysku, NIE na GitHubie)

Zmiany (zlecenie użytkownika):
1. **Usunięte MQTT**: `mqtt_publisher.py` (skasowany), opcje `mqtt_*`
   z `config.py`, import/publikacja z `__main__.py`, `paho-mqtt`
   z `requirements.txt`, sekcja MQTT w README. Grep `mqtt|MQTT|paho`
   po zmianach: 0 trafień w projekcie.
2. **Względny czas ostatniej aktualizacji** ("ostatnia aktualizacja:
   10 min temu") — `store.py`: stała `STALE_AFTER_MINUTES = 30` +
   funkcja `age_minutes()`; snapshot zwraca `age_minutes` i `stale`.
   `server.py`: helper `_age_pl()` (PL: "przed chwilą", "10 min temu",
   "2 godz. 15 min temu", "1 dzień i 3 godz. temu") + `_update_line()`.
   Pokazywane: strona główna (meta pod h1), `/breaking` (w nagłówku),
   `/api/status` (`age_minutes`, `stale`).
3. **Ostrzeżenie >30 min**: gdy `stale` — strona główna dostaje
   `.warn` "⚠ Problem z pobieraniem danych — ostatnia aktualizacja jest
   starsza niż 30 min"; `/breaking` — stamp zmienia klasę na `stale`
   (pomarańcz, bold, w trybie dark #ffb74d) i tekst "⚠ problem z
   pobieraniem danych — ostatnia aktualizacja: X". JS auto-refreshu
   kopiuje też `className` stampu (nie tylko textContent).
4. **`/breaking` bez nagłówka i licznika**: usunięto `<h1>Pilne — Onet</h1>`,
   `<span id="meta">N wiadomości` i licznik "shown / total · odśw. co 60 s"
   z JS; w nagłówku zostały: pulsująca kropka + czas ostatniej aktualizacji.
5. **Dokumentacja**: README (intro bez MQTT, tabela endpunktów z
   `age_minutes`/`stale`, opis `/breaking` z nowym nagłówkiem, tabela
   opcji bez `MQTT_HOST` + akapit "Wiek danych", struktura projektu bez
   `mqtt_publisher.py`); DOCS.md (przykład `/api/status` z `age_minutes`
   + `stale` i ich opis, nowa sekcja `GET /breaking` HTML).
6. **Wersja**: `config.yaml` i `__init__.py` → **1.1.0**.

Sprawdzone: tokeny `@@...@@` w szablonach 1:1 z `.replace()`, grep MQTT
czysty, `__main__.py` bez publisher.

### TODO (kolejność)
1. **Użytkownik wgruje na GitHub main** (Web UI): `onet_news/app/server.py`,
   `onet_news/app/store.py`, `onet_news/app/config.py`,
   `onet_news/app/__main__.py`, `onet_news/app/__init__.py`,
   `onet_news/requirements.txt` (bez paho-mqtt), `onet_news/config.yaml`
   (wersja 1.1.0), usunięcie `onet_news/app/mqtt_publisher.py`,
   `README.md`, `onet_news/DOCS.md` (i opcjonalnie `STATUS.md`).
2. **CI** zbierze się sam → obraz 1.1.0 + latest w GHCR.
3. **Użytkownik klika Update** w HA (Ustawienia → Aplikacje → Onet News).
4. Weryfikacja: `/breaking` bez nagłówka, "ostatnia aktualizacja: X min
   temu", `/api/status` z `age_minutes`/`stale`.

**STATUS 1.1.0 (2026-11-19): ZROBIONE** — user wgrał pliki na main, CI
zbudował 1.1.0 do GHCR, user zaktualizował appę w HA.

## WERSJA 1.2.0 (sesja 2026-11-19 — na dysku, NIE na GitHubie)

Zlecenie: "dodać obsługę artykułów z wp.pl, taka sama zasada + możliwość
włączenia źródeł w konfiguracji onet.pl i wp.pl".

### Źródła WP (zweryfikowane live; GraphQL = dead end, RSS 404)

Czysty statyczny HTML (ta sama zasada co Onet):
1. **`https://www.wp.pl/`** — SSR teasery z atrybutem `data-bdbd`
   (HTML-escaped JSON, `&#34;` = `"`). 184 kotwice: 151 `sgTeaser`,
   27 `sgTextlink`. **Kategoria `600` = główny strumień (115 pozycji)**.
   Pola: `type`, `categoryId`, `dotParams.{cid,ctype}` (article/video),
   `pinned`. Tytuł: `h3.wp-teaser-title` / `span.wp-text-link-title`;
   obraz: `v.wpimg.pl`; sponsorowane: `.wp-teaser-sponsored-label`.
   **Brak czasu publikacji** na homepage.
2. **`https://wiadomosci.wp.pl/`** — sekcja **"Najnowsze"**:
   `a.timeline-entry > time[datetime]` (UTC, np. `12:39Z` = 13:39 PL)
   + `h3` tytuł — 35 pozycji = odpowiednik livebaru (breaking z czasami).

Kategorie WP: z **domeny URL** (jak Onet): `sportowefakty.wp.pl` → sport,
`finanse.wp.pl` → finanse, `pogoda.wp.pl` → pogoda itd.

### Zmiany kodu (wszystko na dysku, testy zielone)

- **NOWY `app/wp_scraper.py`** — `WpScraper`: `_parse_home` (data-bdbd,
  cat 600, filtry: sponsored, SKIP_TITLE_MARKERS, dedup po URL) +
  `_parse_timeline` (timeline-entry, `datetime` UTC → `_sort_min`).
- **NOWY `app/aggregator.py`** — `Aggregator`: źródła w równoległych
  wątkach (awaria jednego nie blokuje drugiego), breaking scalane po
  czasie (nowe na górze, `_breaking_key` z `_sort_min`), ranking spleciony
  `_interleave` (onet #1, wp #1, …) z **wyłączonym pilnymi**, status
  per źródło (`sources`, `all_ok`).
- `app/models.py` — `Article.site: str = "onet"`.
- `app/scraper.py` — `scrape()` zwraca obiekty `Article` (agregator robi
  `to_dict`); `livebar_sort_minutes()` przybliża HH:MM (CEST/CET wg
  miesiąca) → `_sort_min` dla merge'u.
- `app/config.py` — `_bool()` + opcje `enable_onet`/`enable_wp`
  (env `ENABLE_ONET`/`ENABLE_WP`, default True) + `Settings.enabled_sources`.
- `app/__main__.py` — `Aggregator` zamiast `OnetScraper`; log
  "scrape ok: %d articles, %d breaking (onet: %d, wp: %d)".
- `app/store.py` — `all_ok` (status degraded gdy zawiedzie 1 źródło);
  fix: bez danych + błąd → `degraded` (nie `waiting`).
- `app/server.py` — tagi źródła (`Onet`/`WP`) w `_article_li`, sekcja
  **"Źródła"** w `PAGE` (`@@SOURCES@@`), tytuły "Pilne — Onet i WP",
  **fix `_limit()`** — `/api/articles` i `/api/popular` wracały 500
  (funkcja istniała tylko w użyciu, nie w definicji!).
- `config.yaml` — **1.2.0**, `enable_onet`/`enable_wp: bool` w schemacie,
  description z wp.pl.
- `translations/pl.yaml` — "Włącz Onet.pl" / "Włącz WP.pl".
- `CHANGELOG.md` (wpis 1.2.0), `DOCS.md` (sources/all_ok, breaking z obu,
  pole `site`, ranking spleciony), `README.md` (WP, przełączniki, struktura).

### Testy (2026-11-19, lokalnie, Python 3.14 + venv `Temp\opencode\hanevs`)

- Live scrape: Onet 60 art. + 10 pilnych, WP 113 art. + 35 pilnych;
  merge breaking 45 (posortowane: onet 14:39 → wp "16 min" → …).
- Edge cases: tylko onet / tylko wp / wp fails (degraded, onet served) /
  oba fail / oba wyłączone (błąd w statusie).
- Serwer Flask na :8099: `/api/status` (sources, all_ok), `/api/articles`
  (60 = 30+30 splecione), `/api/popular` (30, Onet), `/api/feeds` (12),
  `/api/breaking` (45), `/healthz`, `/` (sekcja Źródła: "ok — 60 artykułów,
  10 pilnych"), `/breaking` w przeglądarce (etykiety, filtry, bez błędów JS).

### Rename folderu + wydzielony Onet (2026-11-19, 1.2.1 — na dysku)

- `onet_news/` → **`news/`** (apka zawiera Onet + WP; folder nie musi być
  zgodny ze slugiem — zweryfikowane w kodzie supervisora:
  `supervisor/store/data.py` → `app_slug = f"{repository}_{app['slug']}"`,
  slug pochodzi z **`slug` w `config.yaml`**, a katalogi app wykrywają
  `**/config.*`; CI `find-addons` też dynamiczne).
- **Slug zostaje `onet_news`** (celowo!) — dzięki temu apka w HA
  (ID `b6f664cb_onet_news`) zaktualizuje się in-place: ten sam token
  ingress, karta na dashboardzie bez zmian, brak potrzeby reinstalacji.
- `app/scraper.py` → **`app/onet_scraper.py`** (wzór: `wp_scraper.py`);
  importy zaktualizowane w `aggregator.py` i `wp_scraper.py`; logger
  `onet_news` → `news` (`__main__.py`).
- Wersja: **1.2.1** (`config.yaml`, `__init__.py`), wpis w `CHANGELOG.md`;
  README: struktura + ścieżki (`cd news`, `news/config.yaml`).
- Testy: `py_compile` OK, live (onet 60+10, wp 114+35, breaking 45),
  edge cases OK, serwer :8099 (endpointy 200).

### TODO (kolejność)

1. **Użytkownik wgruje na GitHub main** (Web UI): utworzyć folder **`news/`**
   i wgrać do niego (nowa ścieżka!): `app/__init__.py`, `app/__main__.py`,
   `app/config.py`, `app/models.py`, `app/onet_scraper.py` (ZASTĘPUJE
   `scraper.py`), `app/wp_scraper.py`, `app/aggregator.py`, `app/server.py`,
   `app/store.py`, `config.yaml` (1.2.1), `translations/pl.yaml`,
   `CHANGELOG.md`, a potem **usunąć stary folder `onet_news/`** na GitHubie.
   Dodatkowo: `README.md` (zmieniona struktura/ścieżki).
   Uwaga: pliki `DOCS.md`, `Dockerfile`, `requirements.txt` są bez zmian
   (wewnętrzne ścieżki `app/...` nie zależą od nazwy folderu).
2. **CI** zbuduje 1.2.1 do GHCR (find-addons wykryje `news/` automatycznie).
3. **Update w HA** — in-place (ten sam slug `onet_news`); w opcjach appy
   przełączniki "Włącz Onet.pl" / "Włącz WP.pl"; karta "Pilne" bez zmian.
4. Weryfikacja: karta "Pilne" z wpisami z obu źródeł, sekcja "Źródła"
   w panelu, `/api/status.sources`.

## BŁĄD "No changelog found for app b6f664cb_onet_news!" (2026-11-19)

Przy klikaniu Update HA pokazywało w dialogu:
`No changelog found for app b6f664cb_onet_news!` (slug, bo pliku brak).

**Przyczyna (potwierdzona w kodzie supervisora):** `supervisor/apps/model.py`
→ `path_changelog = Path(path_location, "CHANGELOG.md")` — Supervisor szuka
changelogu **w katalogu appy, obok `config.yaml`** (NIE w korzeniu repo).
Endpoint `GET /store/addons/<app>/changelog` zwraca ów plik jako plain text;
frontend pokazuje go w dialogu aktualizacji. Analogicznie `DOCS.md`
(`path_documentation`) — u nas już był.

**Fix (na dysku, do wgrania na GitHub):**
- nowy plik `onet_news/CHANGELOG.md` (wersje 1.1.0 → 1.0.0, po polsku),
- `repository.yaml`: name "HA News" → **"Onet News"** (zgodna nazwa repo
  w store; `name` w `config.yaml` i tak było "Onet News"),
- README: tytuł "Onet News — …", `CHANGELOG.md` w strukturze projektu.

**TODO użytkownika:** wgrać na main: `onet_news/CHANGELOG.md`,
`repository.yaml`, `README.md`. Jeśli po wgraniu dialog nadal pokazuje
błąd → przeładować store (Marketplace → przycisk reload / `POST
/store/reload`) albo zrestartować HA — Supervisor cache'uje pliki repo.

## ZROBIONE (wszystko, co było na liście)

- [x] Apka w HA: **1.0.2** (użytkownik potwierdził "Aktualna wersja: 1.0.2").
- [x] `/breaking` działa w przeglądarce (adres z tokenem, 200, strona
      "Pilne — Onet" z filtrami).
- [x] Karta na dashboardzie: **`custom:cookies-iframe-card`** — użytkownik
      potwierdził **"działa z cookies-iframe"** (2026-11-19).
      (`type: webview` nie istnieje w core HA — stąd wcześniejszy błąd;
      `type: iframe` core byłoby alternatywą, ale bez auto-ciasteczka sesji.)
- [x] README.md + STATUS.md zaktualizowane pod cookies-iframe-card.

## OTWARTE (opcjonalne, użytkownik nie zdecydował)

1. **Wariant HACS** (integracja `custom_components/onet_news` — encje zamiast
   REST: `sensor.onet_news_breaking`, `sensor.onet_news_popular`,
   `button.onet_news_refresh`; bez Docker/GHCR/CI/ingress, bez interaktywnych
   filtrów JS). Użytkownik miał do wyboru: 1) zostajemy z apką, 2) przepiszę
   jako HACS, 3) oboje w tym samym repo. **Decyzji brak** — nie ruszać,
   dopóki użytkownik nie wybierze.
2. Drobne kosmetyki karty: inny `aspect_ratio` (teraz 56%), nagłówek,
   osadzenie w horizontal-stacku.

## Zmiany z sesji 2026-11-18 (wszystko zapisane na dysku)

- `onet_news/app/server.py`:
  - szablon `BREAKING_PAGE` + `render_breaking()` + route `GET /breaking`,
  - filtry: pole wyszukiwania (norm. polskich znaków), chipy kategorii,
    licznik "widoczne / wszystkie", auto-refresh 60 s przez fetch()
    z zachowaniem filtrów,
  - `_article_li(..., show_breaking_tag=...)` — na /breaking brak zbędnego
    taga „pilne", dodane style `.tag`,
  - `/api/endpoints` zawiera `/breaking`.
- `onet_news/config.yaml`: wersja `1.0.0` → `1.0.1` → **`1.0.2`**.
- `README.md`: sekcja "Karta 'Pilne' na dashboardzie"
  (finalnie cookies-iframe-card; początkowo błędnie „Webview").
- Poprawki CI z tej sesji (już na main, runy zielone):
  - `builder.yaml`: pusty changed-files (pierwszy push) → buduj wszystkie,
  - `build-app.yaml`: job `manifest` używa `needs.prepare.outputs.*`
    (nie `steps.normalize.*` z innego joba) — 1:1 z wzorca apps-example.

## Fakt techniczny do zapamiętania

- HA użytkownika: ingress pod **`/api/hassio_ingress/<token>/...`**
  (proxy OpenResty przed HA). Karta iframe musi używać tej samej domeny
  i HTTPS — port 8080 z LAN nie działa zdalnie (mixed content).
- Identyfikatory: ID appy `b6f664cb_onet_news` ≠ token ingress
  (`v56jESc-TGu2ZJDq7WLdg_MFzCUfrCIQ-sgSo1gZuEo`).

## Środowisko

- Windows + PowerShell 5 (skrypty diagnostyczne jako .ps1 w
  C:\Users\Rafal\AppData\Local\Temp\opencode, bez znaków nie-ASCII).
- **Python 3.14.10 DOSTĘPNY** (od 2026-11-19 — wcześniej były tylko stuby
  z MS Store); venv do testów: `C:\Users\Rafal\AppData\Local\Temp\opencode\hanevs`
  (requests, beautifulsoup4, flask). Testy: `Temp\opencode\test_ha_news.py`
  (live) i `test_edge.py` (edge cases).
- Brak lokalnego git — pliki wgruje użytkownik ręcznie przez GitHub Web UI.
- Użytkownik komunikuje się po polsku.
