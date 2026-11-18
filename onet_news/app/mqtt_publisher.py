"""Optional MQTT integration.

When MQTT_HOST is set (environment or app options), the app publishes:

- an MQTT discovery sensor ``sensor.onet_news_top`` with the top 5
  ranked articles (JSON payload) on every successful scrape,

so Home Assistant (with an MQTT broker) gets a ready-to-use entity.
"""
from __future__ import annotations

import json
import logging

from .config import Settings

log = logging.getLogger(__name__)

ENTITY_ID = "onet_news_top"


class MqttPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = None
        if not settings.mqtt_enabled:
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            log.warning("paho-mqtt is not installed, MQTT publishing disabled")
            return
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="ha_onet_news",
            )
        except TypeError:  # paho-mqtt 1.x
            self.client = mqtt.Client(client_id="ha_onet_news")
        if settings.mqtt_user:
            self.client.username_pw_set(settings.mqtt_user, settings.mqtt_password or None)
        try:
            self.client.connect(settings.mqtt_host, settings.mqtt_port)
            self.client.loop_start()
            self._publish_discovery()
            log.info(
                "MQTT connected: %s:%s", settings.mqtt_host, settings.mqtt_port
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("MQTT connection failed: %s", exc)
            self.client = None

    def _publish_discovery(self) -> None:
        if self.client is None:
            return
        base = f"{self.settings.mqtt_topic}/sensor/{ENTITY_ID}"
        payload = {
            "name": "Onet - najciekawsze",
            "unique_id": f"ha_{ENTITY_ID}",
            "icon": "mdi:newspaper-variant-outline",
            "state_topic": f"{base}/state",
            "json_attributes_topic": f"{base}/state",
        }
        self.client.publish(f"{base}/config", json.dumps(payload), qos=1, retain=True)

    def publish(self, result: dict) -> None:
        if self.client is None:
            return
        try:
            top = result.get("articles") or []
            payload = json.dumps(
                [{"title": a.get("title"), "url": a.get("url")} for a in top[:5]],
                ensure_ascii=False,
            )
            topic = f"{self.settings.mqtt_topic}/sensor/{ENTITY_ID}/state"
            self.client.publish(topic, payload, qos=1, retain=True)
        except Exception as exc:  # noqa: BLE001
            log.warning("MQTT publish failed: %s", exc)
