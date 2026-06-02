"""
Sabereen News Explosion Monitor
Monitors the public Telegram channel @SabrenNewss (Arabic) for reports of
explosions / strikes across the Middle East and emits structured alerts.

Reads the public web preview (https://t.me/s/SabrenNewss) with aiohttp +
BeautifulSoup — no MTProto credentials required. Each qualifying post is
geocoded and classified, then handed to the callback so the orchestrator can
render a map and post it to the channel.

Conforms to the standard source interface: async run() / async stop(), a
constructor taking an on_alert_callback, and in-memory deduplication.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from config.settings import (
    SABREN_CHANNEL,
    SABREN_POLL_INTERVAL,
    SABREN_TRIGGER_KEYWORDS,
)
from utils.me_geocoder import geocode
from utils.attack_formatter import classify_attack, is_confirmed

logger = logging.getLogger(__name__)

SABREN_WEB_URL = f"https://t.me/s/{SABREN_CHANNEL}"


class SabrenAlert:
    """A geocoded explosion/strike report extracted from a Sabereen News post."""

    def __init__(self, text: str, message_id: int, timestamp: datetime,
                 location: dict, type_en: str, type_ar: str, confirmed: bool):
        self.text = text
        self.message_id = message_id
        self.timestamp = timestamp
        self.location = location          # dict from geocode(): name_en/name_ar/lat/lon/country
        self.type_en = type_en
        self.type_ar = type_ar
        self.confirmed = confirmed
        self.link = f"https://t.me/{SABREN_CHANNEL}/{message_id}"
        self.id = f"{SABREN_CHANNEL}:{message_id}"

    @property
    def excerpt(self) -> str:
        """A short single-line excerpt of the original post."""
        return " ".join(self.text.split())[:280]


class SabrenNewsMonitor:
    """Polls the Sabereen News web preview for explosion/strike reports."""

    def __init__(self, on_alert_callback):
        self.callback = on_alert_callback
        self.seen_ids: set[str] = set()
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._keywords = [k.lower() for k in SABREN_TRIGGER_KEYWORDS]
        self._primed = False  # first poll seeds dedup without emitting backlog

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout, trust_env=True)
        return self._session

    def _matches(self, text: str) -> bool:
        low = text.lower()
        return any(kw in low for kw in self._keywords)

    @staticmethod
    def _parse_timestamp(raw: Optional[str]) -> datetime:
        if raw:
            try:
                # Telegram uses e.g. "2026-06-02T18:30:05+00:00"
                return datetime.fromisoformat(raw).astimezone(timezone.utc)
            except (ValueError, TypeError):
                pass
        return datetime.now(timezone.utc)

    async def fetch_posts(self) -> list[SabrenAlert]:
        """Fetch and parse the latest posts into SabrenAlert objects."""
        session = await self._get_session()
        try:
            async with session.get(SABREN_WEB_URL) as resp:
                if resp.status != 200:
                    logger.warning(f"Sabereen fetch HTTP {resp.status}")
                    return []
                html = await resp.text()
        except aiohttp.ClientError as e:
            logger.error(f"Sabereen network error: {e}")
            return []

        soup = BeautifulSoup(html, "html.parser")
        alerts: list[SabrenAlert] = []

        for wrap in soup.select("div.tgme_widget_message"):
            data_post = wrap.get("data-post", "")
            try:
                message_id = int(data_post.split("/")[-1])
            except (ValueError, IndexError):
                continue

            text_el = wrap.select_one(".tgme_widget_message_text")
            text = text_el.get_text(separator=" ", strip=True) if text_el else ""
            if not text or not self._matches(text):
                continue

            location = geocode(text)
            if not location:
                # No mappable location → can't draw a map; skip.
                continue

            time_el = wrap.select_one("time[datetime]")
            ts = self._parse_timestamp(time_el.get("datetime") if time_el else None)
            type_en, type_ar = classify_attack(text)
            confirmed = is_confirmed(text)

            alerts.append(SabrenAlert(
                text=text, message_id=message_id, timestamp=ts,
                location=location, type_en=type_en, type_ar=type_ar,
                confirmed=confirmed,
            ))

        return alerts

    async def poll_once(self):
        posts = await self.fetch_posts()
        new_alerts = []
        for alert in posts:
            if alert.id not in self.seen_ids:
                self.seen_ids.add(alert.id)
                new_alerts.append(alert)

        # Trim dedup set periodically, keeping the most recent (highest) message
        # IDs so we never evict recent posts and re-emit them as "new".
        if len(self.seen_ids) > 1000:
            def _mid(idv: str) -> int:
                try:
                    return int(idv.split(":")[-1])
                except ValueError:
                    return 0
            self.seen_ids = set(sorted(self.seen_ids, key=_mid)[-500:])

        # On the very first poll, just seed dedup so we don't replay the backlog.
        if not self._primed:
            self._primed = True
            logger.info(f"Sabereen monitor primed with {len(new_alerts)} recent post(s)")
            return

        if new_alerts:
            # Oldest first so the channel reads chronologically.
            new_alerts.sort(key=lambda a: a.message_id)
            await self.callback(new_alerts)

    async def run(self):
        """Main polling loop."""
        self._running = True
        logger.info("🟢 Sabereen News explosion monitor started")
        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"Error in Sabereen poll loop: {e}")
            await asyncio.sleep(SABREN_POLL_INTERVAL)

    async def stop(self):
        """Stop the monitor and close the session."""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("🔴 Sabereen News monitor stopped")
