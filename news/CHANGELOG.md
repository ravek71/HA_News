# Changelog — Onet News

## 1.2.1

- Zmiana struktury projektu: główny folder `onet_news/` → `news/` (apka
  zawiera już nie tylko Onet, ale i WP).
- Wydzielony moduł Onetu: `app/scraper.py` → `app/onet_scraper.py`
  (spójnie z `wp_scraper.py`); bez zmian funkcjonalnych.

## 1.2.0

- **Nowe źródło: WP.pl** (taka sama zasada jak Onet):
  - ranking — główny strumień strony głównej wp.pl (teasery SSR z atrybutem
    `data-bdbd`, kategoria 600),
  - wiadomości pilne — oś czasu „Najnowsze" na wiadomosci.wp.pl
    (z datami publikacji, odpowiednik livebaru Oneta),
  - bez JavaScript i bez niepublicznego API — czysty statyczny HTML.
- **Przełączniki źródeł w opcjach appy**: `Włącz Onet.pl` / `Włącz WP.pl`
  (oba domyślnie włączone). Źródła scrapowane są równolegle — awaria jednego
  nie blokuje drugiego.
- Lista pilnych (`/breaking` i `GET /api/breaking`) łączy oba źródła,
  posortowana po czasie (najnowsze na górze); każdy artykuł ma etykietę
  źródła (Onet / WP).
- Ranking na stronie app łączy oba źródła naprzemiennie (onet #1, wp #1, ...)
  — pilne nie mieszają się z rankingiem (mają własną sekcję i stronę).
- Nowa sekcja „Źródła" na stronie app: status każdego źródła (ok / błąd /
  wyłączone + liczba pobranych artykułów).
- `GET /api/status`: nowe pole `sources` (status per źródło) i `all_ok`;
  status `degraded` także gdy zawiedzie tylko jedno z aktywnych źródeł.
- W polach API (`/api/articles`, `/api/breaking`) każdy artykuł ma nowe pole
  `site` (`"onet"` | `"wp"`).
- Poprawka: gdy brak danych i pierwsze odświeżenie się nie powiodło, status
  to `degraded` (nie `waiting`).
- Poprawka: `GET /api/articles` i `GET /api/popular` zwracały błąd 500
  (brakująca funkcja limitująca `?limit=`) — teraz działają.

## 1.1.0

- Usunięto wsparcie dla MQTT (plik `mqtt_publisher.py`, zależność `paho-mqtt`,
  opcje `MQTT_HOST`/`MQTT_USER`/`MQTT_PASSWORD`/`MQTT_PORT`/`MQTT_TOPIC`).
- Względny czas ostatniej aktualizacji na stronach app i na stronie `/breaking`:
  „ostatnia aktualizacja: 10 min temu" (wcześniej pełna data UTC).
- Ostrzeżenie o problemie z pobieraniem danych, gdy ostatnia udana aktualizacja
  jest starsza niż **30 min** (pomarańczowy komunikat w UI oraz pola
  `age_minutes` i `"stale": true` w `GET /api/status` — do automacji).
- Strona `/breaking`: usunięto nagłówek „Pilne — Onet" oraz licznik
  artykułów — w nagłówku pozostaje tylko pulsująca kropka i czas ostatniej
  aktualizacji.
- Poprawki dokumentacji (README.md, DOCS.md).

## 1.0.2

- Strona `/breaking`: wyszukiwanie w tytułach (niezależne od polskich
  znaków) i filtry kategorii (chipy z licznikami).
- Auto-refresh co 60 s z zachowaniem aktywnych filtrów.
- Tryb jasny/ciemny, transparentne tło pod kartę dashboardu.

## 1.0.1

- Nowa strona `/breaking` — lista wiadomości pilnych z livebaru z godzinami
  publikacji (przeznaczona do osadzenia w karcie dashboardu).

## 1.0.0

- Wersja początkowa: scraping Onet.pl (główny feed „O tym się mówi" + livebar
  z wiadomościami pilnymi), deduplikacja i ranking artykułów.
- REST API: `GET /api/articles`, `GET /api/popular`, `GET /api/breaking`,
  `GET /api/feeds`, `GET /api/status`, `POST /api/refresh`, `GET /healthz`.
- Panel app w pasku bocznym Home Assistant (ingress).
