"""
Pikud HaOref (Home Front Command) Alert Monitor
Polls the official Israeli alert API for real-time rocket/missile sirens.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from config.settings import (
    PIKUD_HAOREF_URL,
    PIKUD_HAOREF_HISTORY_URL,
    PIKUD_HAOREF_HEADERS,
    PIKUD_HAOREF_POLL_INTERVAL,
    AREA_TRANSLATIONS,
)

logger = logging.getLogger(__name__)


class PikudHaorefAlert:
    """Represents a single alert from the Home Front Command."""

    def __init__(self, raw_data: dict):
        self.raw = raw_data
        self.id = raw_data.get("id", "")
        self.cat = raw_data.get("cat", "")           # Category (e.g., "1" = rockets)
        self.title = raw_data.get("title", "")        # Alert type in Hebrew
        self.data = raw_data.get("data", [])           # List of areas
        self.desc = raw_data.get("desc", "")           # Description
        self.timestamp = datetime.now(timezone.utc)

    @property
    def areas_hebrew(self) -> list[str]:
        """Return raw Hebrew area names."""
        if isinstance(self.data, list):
            return self.data
        return [self.data] if self.data else []

    @property
    def areas_english(self) -> list[str]:
        """Translate area names to English where possible."""
        translated = []
        for area in self.areas_hebrew:
            entry = AREA_TRANSLATIONS.get(area)
            if entry:
                eng = entry[0] if isinstance(entry, tuple) else entry
                translated.append(eng)
            else:
                translated.append(area)
        return translated

    @property
    def areas_arabic(self) -> list[str]:
        """Translate area names to Arabic where possible."""
        translated = []
        for area in self.areas_hebrew:
            entry = AREA_TRANSLATIONS.get(area)
            if entry and isinstance(entry, tuple) and len(entry) > 1:
                translated.append(entry[1])
            else:
                translated.append(area)
        return translated

    @property
    def areas_trilingual(self) -> list[tuple[str, str, str]]:
        """Return (english, arabic, hebrew) tuples for each area."""
        result = []
        for area in self.areas_hebrew:
            entry = AREA_TRANSLATIONS.get(area)
            if entry and isinstance(entry, tuple):
                result.append((entry[0], entry[1], area))
            else:
                result.append((area, area, area))
        return result

    @property
    def alert_type(self) -> str:
        """Determine the type of alert based on category."""
        cat_map = {
            "1": "🚀 Rocket / Missile Alert",
            "2": "🚀 Rocket / Missile Alert",
            "3": "⚠️ Earthquake Alert",
            "4": "☣️ Hazardous Materials",
            "5": "🌊 Tsunami Alert",
            "6": "🛩️ Hostile Aircraft Intrusion",
            "7": "⚠️ Non-Conventional Threat",
            "13": "⚠️ Terror Infiltration",
        }
        return cat_map.get(str(self.cat), f"⚠️ Alert (Category {self.cat})")

    def __eq__(self, other):
        if not isinstance(other, PikudHaorefAlert):
            return False
        return self.id == other.id and set(self.areas_hebrew) == set(other.areas_hebrew)

    def __hash__(self):
        return hash((self.id, tuple(sorted(self.areas_hebrew))))


class PikudHaorefMonitor:
    """
    Continuously polls the Pikud HaOref alert API.
    Yields new alerts via an async callback.
    """

    def __init__(self, on_alert_callback):
        self.callback = on_alert_callback
        self.seen_alerts: set[str] = set()
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def fetch_alerts(self) -> list[PikudHaorefAlert]:
        """Fetch current active alerts from Pikud HaOref."""
        try:
            session = await self._get_session()
            async with session.get(
                PIKUD_HAOREF_URL, headers=PIKUD_HAOREF_HEADERS
            ) as response:
                if response.status != 200:
                    logger.warning(f"Pikud HaOref API returned status {response.status}")
                    return []

                text = await response.text()
                text = text.strip()

                # The API sometimes returns empty response when no alerts
                if not text or text == "null":
                    return []

                # Handle BOM if present
                if text.startswith('\ufeff'):
                    text = text[1:]

                data = json.loads(text)

                if isinstance(data, dict):
                    return [PikudHaorefAlert(data)]
                elif isinstance(data, list):
                    return [PikudHaorefAlert(item) for item in data]
                return []

        except json.JSONDecodeError as e:
            logger.debug(f"No active alerts (empty/invalid JSON): {e}")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Pikud HaOref alerts: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching alerts: {e}")
            return []

    async def fetch_history(self) -> list[dict]:
        """Fetch recent alert history."""
        try:
            session = await self._get_session()
            async with session.get(
                PIKUD_HAOREF_HISTORY_URL, headers=PIKUD_HAOREF_HEADERS
            ) as response:
                if response.status != 200:
                    return []
                text = await response.text()
                if text.startswith('\ufeff'):
                    text = text[1:]
                return json.loads(text) if text.strip() else []
        except Exception as e:
            logger.error(f"Error fetching alert history: {e}")
            return []

    def _make_dedup_key(self, alert: PikudHaorefAlert) -> str:
        """Create a deduplication key for an alert."""
        areas_str = "|".join(sorted(alert.areas_hebrew))
        return f"{alert.cat}:{areas_str}:{alert.timestamp.strftime('%Y%m%d%H%M')}"

    async def poll_once(self):
        """Single poll iteration — fetch and process new alerts."""
        alerts = await self.fetch_alerts()
        new_alerts = []

        for alert in alerts:
            key = self._make_dedup_key(alert)
            if key not in self.seen_alerts:
                self.seen_alerts.add(key)
                new_alerts.append(alert)

                # Trim dedup set if it gets too large
                if len(self.seen_alerts) > 1000:
                    # Keep only the most recent half
                    items = list(self.seen_alerts)
                    self.seen_alerts = set(items[len(items)//2:])

        if new_alerts:
            await self.callback(new_alerts)

    async def run(self):
        """Main polling loop."""
        self._running = True
        logger.info("🟢 Pikud HaOref monitor started")

        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"Error in Pikud HaOref poll loop: {e}")
            await asyncio.sleep(PIKUD_HAOREF_POLL_INTERVAL)

    async def stop(self):
        """Stop the monitor and close the session."""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("🔴 Pikud HaOref monitor stopped")
