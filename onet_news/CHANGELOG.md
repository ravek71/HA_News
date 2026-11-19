# Changelog — Onet News

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
