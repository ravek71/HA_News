# HA News — add-on Home Assistant: wiadomości z Onet.pl

[![Dodaj repozytorium do Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fravek71%2FHA_News)

Aplikacja (add-on) dla Home Assistant, która scrapuje **najciekawsze artykuły
z Onet.pl** i udostępnia je przez **REST API** (JSON). Po zainstalowaniu ma
własny **panel w pasku bocznym HA** (ingress) z podglądem top newsów,
wiadomości pilnych i statusu.

## Jak to działa

Onet.pl nie ma publicznego RSS, więc app używa tych samych źródeł danych,
których używa strona główna onet.pl:

1. **Strona główna** `https://www.onet.pl/` — ze zagnieżdżonej konfiguracji
   JSON app wyciąga:
   - URL iframe'a **livebar** (wiadomości pilne; UUID zmienia się przy każdym
     odświeżeniu strony, więc jest pobierany na bieżąco),
   - **UUID feedów** wszystkich sekcji strony głównej.
2. **API feedów** `https://mp-feed-api.onet.pl/2.0/feeds/<uuid>` — zwraca pełne
   dane artykułów w JSON dla każdej sekcji:
   „O tym się mówi" (= *najpopularniejsze dziś w Onecie*), „Wybrane dla Ciebie",
   „Wiadomości", „Sport", „Biznes" i inne.
3. **Livebar** `https://livebar.onet.pl/desktop/<uuid>` — serwisy HTML z
   wiadomościami pilnymi i godzinami publikacji.

Artykuły są deduplikowane (po URL), wzbogacane kategorią (z domeny/sekcji URL),
a następnie rankowane według heurystyki: własny wskaźnik ważności Onet
(`hardness`) + liczba reakcji (`emotions`) + pozycja w feędzie (własny ranking
Onet) + bonus dla wiadomości pilnych.

## Endpunkty REST API

Adres bazowy: `http://<adres-HA>:8080` (mapowanie portu 8080/tcp).

| Endpunkt | Opis |
|---|---|
| `GET /api/articles?limit=60&include_breaking=1` | wszystkie artykuły, posortowane wg punktu |
| `GET /api/popular?limit=30` | feed „O tym się mówi" w oryginalnej kolejności (najpopularniejsze) |
| `GET /api/breaking` | wiadomości pilne z livebar (z godziną) |
| `GET /api/feeds` | wykryte feedy (sekcje) z liczbą artykułów |
| `GET /api/status` | status scrapowania: `age_minutes` (wiek ostatniej aktualizacji), `stale` (problem z pobieraniem, gdy >30 min), błędy, URL livebar |
| `POST /api/refresh` | wymuś odświeżenie teraz (w tle) |
| `GET /breaking` | strona HTML — tylko pilne, filtry, auto-refresh (do karty na dashboardzie) |
| `GET /healthz` | health check (watchdog) |

Przykład zwracanej pozycji:

```json
{
  "title": "Nowa prognoza Onetu. Rekordowa przewaga KO nad PiS",
  "url": "https://wiadomosci.onet.pl/kraj/nowa-prognoza-wyborcza-onetu-.../xq52888",
  "image": "https://ocdn.eu/pulscms/MDA_/830ab2db....png",
  "source": "Onet",
  "section": "O tym się mówi",
  "category": "kraj",
  "kind": "article",
  "is_premium": true,
  "summary": "Krótki opis artykułu…",
  "authors": ["Jan Kowalski"],
  "reactions": 1856,
  "hardness": 5,
  "published": null,
  "breaking": false,
  "score": 123.4
}
```

Wpisy z livebar mają dodatkowo `"published": "10:56"` i `"breaking": true`.

## Instalacja

### Opcja A — repozytorium custom (zalecane)

1. Wrzuć projekt na GitHub jako **publiczne** repozytorium
   `https://github.com/ravek71/HA_News` (plik `repository.yaml`,
   `onet_news/config.yaml` i badge są już skonfigurowane dla tego loginu;
   przy forku zmień `url`/`image`/`ghcr.io/...` na swój).
2. Utwórz na GitHubzie pusty **publiczny** repozytorium pakietów: po pierwszym
   zbudowaniu pakiet `ghcr.io/ravek71/onet-news` jest prywatny — zmień jego
   widoczność na publiczną (GitHub → Packages → `onet-news` → Change package
   visibility). Inaczej HA nie pobra obrazu.
3. Workflowy w `.github/workflows` zbudują i opublikują obraz (multi-arch)
   automatycznie przy każdym `push` na `main`.
4. W Home Assistant: **Ustawienia → Aplikacje → Zainstaluj aplikację →
   (menu w prawym górnym rogu) Repozytoria → Dodaj** i podaj URL:
   `https://github.com/ravek71/HA_News`
5. Zainstaluj aplikację **Onet News** i gotowe.
   W zakładce aplikacji jest przycisk **Open Web UI** (albo włącz
   **Show in sidebar** — ikona gazety w pasku bocznym).

### Opcja B — zwykły Docker (bez repozytorium)

```bash
cd onet_news
docker build -t ha-onet-news .
docker run -d --name onet-news --restart unless-stopped \
  -p 8080:8099 \
  -e INTERVAL_MINUTES=10 -e MAX_ARTICLES=60 \
  ha-onet-news
```

Sprawdzenie: `curl http://localhost:8080/api/status`

## Użycie w Home Assistant

### Karta „Pilne" na dashboardzie (iframe z sesją ingress)

App ma dedykowaną stronę **`/breaking`** — tylko wiadomości pilne z livebaru:
pulsująca czerwona kropka, **wiek ostatniej aktualizacji** („ostatnia
aktualizacja: 10 min temu"; gdy dane są starsze niż 30 min — pomarańczowe
ostrzeżenie o problemie z pobieraniem), lista z godzinami, **pole
wyszukiwania** (z obsługą polskich znaków) i **filtry kategorii** (chipy
generowane z bieżącej listy), auto-refresh co 60 s z zachowaniem wybranych
filtrów, tryb jasny/ciemny.

Strona jest serwowana przez **ingress** (ta sama domena i protokół co HA),
więc do osadzenia w karcie trzeba iframe'a, który sam zaopatrzy się w
ciasteczko sesji supervisor — to robi karta custom
**[cookies-iframe-card](https://github.com/louisslee/cookies-iframe-card)**
(jeden plik JS; `type: webview` **nie istnieje** w core HA).

1. **Instalacja karty** (raz):
   - **HACS**: *Frontend* → *+* (dodaj repozytorium) →
     `louisslee/cookies-iframe-card` → *Download*, albo
   - **ręcznie**: pobierz
     `https://raw.githubusercontent.com/louisslee/cookies-iframe-card/main/dist/cookies-iframe-card.js`
     do folderu `www/` katalogu konfiguracji HA i zarejestruj zasób:
     *Ustawienia → Panele → (dashboard) → ⋮ → Zasoby → Dodaj* z URL
     `/local/cookies-iframe-card.js`, typ: *Moduł JavaScript (JavaScript module)*.
2. **Adres strony**: otwórz panel **Onet News** z paska bocznego HA i weź
   z paska przeglądarki prefiks do `/api/hassio_ingress/<TOKEN>/`
   (prefiks bywa też `/api/ingress/` — zależy od wersji HA), doklej `/breaking`:

   ```
   https://<twoj-adres-HA>/api/hassio_ingress/<TOKEN>/breaking
   ```
3. **Karta** (dashboard → *Dodaj kartę* → *custom* → *Cookies Iframe Card*,
   albo YAML):

   ```yaml
   type: custom:cookies-iframe-card
   title: Pilne — Onet
   url: https://<twoj-adres-HA>/api/hassio_ingress/<TOKEN>/breaking
   aspect_ratio: 56%
   ```

Uwagi:
- adres musi być z **tej samej domeny i protokołu** co HA (HTTPS), inaczej
  przeglądarka zablokuje iframe (mixed content); port 8080 z LAN nie jest
  potrzebny,
- `TOKEN` to długi łańcuch z adresu panelu (nie ID appy, np.
  `b6f664cb_onet_news`); zmienia się tylko przy usunięciu i reinstalacji appy,
- `aspect_ratio` to **procent szerokości** karty (56% ≈ 16:9, 100% = kwadrat),
- karta odświeża ciasteczko sesji co 10 min, więc iframe nie „wygasa".

### Sensor przez integrację `rest`

```yaml
sensor:
  - platform: rest
    name: "Onet - top news"
    unique_id: "onet_top_news"
    resource: "http://192.168.1.10:8080/api/popular?limit=5"
    value_template: "{{ value_json.articles | map(attribute='title') | join(' | ') }}"
  - platform: rest
    name: "Onet - pilne (liczba)"
    unique_id: "onet_breaking_count"
    resource: "http://192.168.1.10:8080/api/breaking"
    value_template: "{{ value_json.count }}"
```

### Powiadomienie o wiadomościach pilnych (przykład automatu)

```yaml
automation:
  - alias: "Onet - wiadomość pilna"
    trigger:
      - platform: state
        entity_id: sensor.onet_breaking_count
    action:
      - service: notify.mobile_app_twoj_telefon
        data:
          title: "Nowa wiadomość pilna z Onetu"
          message: >-
            {{ states('sensor.onet_top_news') }}
```

## Konfiguracja

| Opcja / zmienna | Domyślnie | Opis |
|---|---|---|
| `interval_minutes` | 10 | co ile minut odświeżać dane |
| `max_articles` | 60 | ile artykułów trzymać w pamięci / zwracać |
| `log_level` | `info` | `debug`/`info`/`warning`/`error` |
| `MAX_FEEDS` (env) | 12 | ile feedów pobierać ze strony głównej |
| `FEED_UUIDS` (env) | — | lista UUID (po przecinku) — pominij auto-wykrywanie |

Polecenie `POST /api/refresh` pozwala wymusić odświeżenie bez czekania na cykl.

**Wiek danych:** strony app i `/api/status` pokazują, ile min temu było
ostatnie **udane** odświeżenie (np. „ostatnia aktualizacja: 10 min temu").
Jeśli jest starsze niż **30 min** (`STALE_AFTER_MINUTES`), UI pokazuje
ostrzeżenie o problemie z pobieraniem danych, a `/api/status` zwraca
`"stale": true` — z tego pola można np. zbudować automat powiadamiający.

## Uwagi prawne

Projekt służy do użytku osobistego. Dane Onet.pl są chronione prawem autorskim;
app jedynie odczytuje publicznie dostępne treści. Nie publikuj ich ponownie.

## Struktura projektu

```
HA_News/
├── repository.yaml            # metadane repozytorium (HA app store)
├── .github/workflows/         # CI: build + push obrazu do GHCR
└── onet_news/
    ├── config.yaml            # manifest add-onu (HA)
    ├── Dockerfile
    ├── requirements.txt
    ├── DOCS.md                # szczegółowa dokumentacja API
    ├── translations/pl.yaml
    └── app/
        ├── __main__.py        # pętla scrapera + start serwera
        ├── config.py          # opcje: /data/options.json > env > domyślne
        ├── models.py          # model Article
        ├── scraper.py         # pobieranie i ranking (strona, feed API, livebar)
        ├── server.py          # REST API (Flask) + strony HTML
        └── store.py           # thread-safe magazyn ostatniego wyniku
```
