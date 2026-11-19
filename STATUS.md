# STATUS — stan projektu HA_News

Ostatnia aktualizacja: 2026-11-19 (popołudnie)

## Stan: wersja 1.1.0 gotowa na dysku (do wgrania na GitHuba); 1.0.2 działa w HA użytkownika

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
- Brak lokalnego Pythona i git (tylko stuby z MS Store) — walidacja kodu
  przez CI; projekt ma katalog `.git`, ale bez zainstalowanego git nie da
  się commitować — pliki wgruje użytkownik ręcznie przez GitHub Web UI.
- Użytkownik komunikuje się po polsku.
