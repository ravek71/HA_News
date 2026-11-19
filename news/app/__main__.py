"""Entry point: background scraper loop + REST API server."""
from __future__ import annotations

import logging
import threading
import time

from .aggregator import Aggregator
from .config import settings
from .server import make_app
from .store import Store

log = logging.getLogger("news")


def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    store = Store()
    aggregator = Aggregator(settings)
    scrape_lock = threading.Lock()

    def do_scrape() -> None:
        if not scrape_lock.acquire(blocking=False):
            log.info("scrape already in progress, skipping")
            return
        try:
            result = aggregator.scrape()
            store.update(result)
            log.info(
                "scrape ok: %d articles, %d breaking (onet: %d, wp: %d)",
                len(result["articles"]),
                len(result["breaking"]),
                result["sources"]["onet"]["articles"],
                result["sources"]["wp"]["articles"],
            )
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            log.exception("scrape failed: %s", exc)
            store.update_error(str(exc))
        finally:
            scrape_lock.release()

    def loop() -> None:
        while True:
            started = time.time()
            do_scrape()
            elapsed = time.time() - started
            sleep_s = max(30.0, settings.interval_minutes * 60.0 - elapsed)
            time.sleep(sleep_s)

    threading.Thread(target=loop, name="scraper", daemon=True).start()

    app = make_app(store, on_refresh=do_scrape)
    log.info("HTTP API listening on 0.0.0.0:%d", settings.port)
    app.run(host="0.0.0.0", port=settings.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
