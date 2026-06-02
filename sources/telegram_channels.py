"""
Israeli Telegram Channel Monitor — TRIGGER-BASED
=================================================

This monitor does NOT listen 24/7. It has two modes:

  IDLE (default):
    - Telethon client is connected but ignores most messages
    - Only "alert-only" channels (Tzofar, Cumta) are passively watched
      as a backup to Pikud HaOref

  ACTIVE (triggered):
    - Activated when Pikud HaOref fires a siren alert
    - Opens a monitoring window (default 10 minutes)
    - ALL 18+ channels are actively scanned for relevant messages
    - On activation, also scrapes recent messages (last 5 min) from
      key channels to catch anything posted just before the siren

Trigger flow:
  Pikud HaOref siren → main.py calls channel_monitor.activate()
                      → ACTIVE mode for 10 min
                      → scrapes recent messages from top channels
                      → listens to all incoming messages
                      → window expires → back to IDLE
"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from telethon import TelegramClient, events

from config.settings import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_PHONE,
    MONITORED_CHANNELS,
    ALERT_KEYWORDS_EN,
    ALERT_KEYWORDS_HE,
    STRICT_WAR_KEYWORDS_EN,
    STRICT_WAR_KEYWORDS_HE,
    ACTIVE_WINDOW_MINUTES,
    SCRAPE_LOOKBACK_MINUTES,
)

logger = logging.getLogger(__name__)


# ─── Channel tiers ───
# Tier 1: Always-on alert channels (backup to Pikud HaOref)
TIER1_ALWAYS_ON = {
    "tzevaadom", "tzevaadom_en",
    "CumtaAlertsChannel", "CumtaAlertsEnglishChannel",
}

# Tier 2: High-priority news — scraped on activation + live during window
# These are the channels Israelis actually check during escalations
TIER2_HIGH_PRIORITY = {
    # Top unofficial channels (biggest audience, fastest reports)
    "abualiexpress", "abu_ali_express_en",
    "Daniel_Amram",
    "amitsegal",
    "HaTzelChannel",
    "sdarotali",
    "news_kodkodgroup",
    "firstreportsnews",
    "israel_news_telegram",
    "tzenzora",
    "hadshotrealtime8",
    # Breaking news aggregators
    "aaborkim", "yaborkim", "newsaborim",
    # Arab affairs desks
    "AbuSalahDesk", "MivzakimMehaMizrah",
    # Security / borders
    "HaCabinetHaBitchoni", "HAFKAK_ARTZI",
    # Official
    "idfofficial", "tzaborkim",
    # Mainstream media
    "N12News", "kann_news", "aaborkim7",
    "YnetNews", "israelhaYomHeb",
}

# Tier 3: Secondary — only live during active window
TIER3_SECONDARY = {
    "intikitnews", "OpIsrael",
    "JewishBreakingNewsTelegram", "IsraelRadar", "ILtoday",
    "Middle_East_Spectator", "ramreports",
}


class TelegramChannelMessage:
    """Represents a filtered message from a monitored Telegram channel."""

    def __init__(self, text: str, channel_name: str, channel_username: str,
                 message_id: int, timestamp: datetime):
        self.text = text
        self.channel_name = channel_name
        self.channel_username = channel_username
        self.message_id = message_id
        self.timestamp = timestamp
        self.id = hashlib.md5(f"{channel_username}:{message_id}".encode()).hexdigest()
        self.link = f"https://t.me/{channel_username}/{message_id}" if channel_username else ""

    @property
    def snippet(self) -> str:
        clean = re.sub(r'\s+', ' ', self.text).strip()
        return clean[:500] + "..." if len(clean) > 500 else clean

    def __eq__(self, other):
        return isinstance(other, TelegramChannelMessage) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


class TelegramChannelMonitor:
    """
    Trigger-based Telegram channel monitor.

    Call activate() to start an active monitoring window.
    Call activate() again to extend the window (e.g., if more sirens fire).
    """

    def __init__(self, on_message_callback):
        self.callback = on_message_callback
        self.seen_ids: set[str] = set()
        self._running = False
        self.client: Optional[TelegramClient] = None

        # ─── State ───
        self._mode = "IDLE"                            # "IDLE" or "ACTIVE"
        self._active_until: Optional[datetime] = None  # When the window closes
        self._activation_count = 0                     # How many times activated today
        self._last_trigger_areas: list[str] = []       # Areas from the triggering siren

        # ─── Resolved entities (cached after first resolution) ───
        self._resolved: dict[str, int] = {}   # username → entity id
        self._tier1_ids: set[int] = set()
        self._tier2_ids: set[int] = set()
        self._tier3_ids: set[int] = set()
        self._all_ids: set[int] = set()

        # ─── Keywords ───
        self.all_keywords = [kw.lower() for kw in ALERT_KEYWORDS_EN + ALERT_KEYWORDS_HE]
        extra = [
            "נפילה", "פגיעה ישירה", "נזק", "פצועים", "הרוגים",
            "יירוט מוצלח", "שברי יירוט", "כיפת ברזל",
            "חץ", "שריקה", "מנהרה", "חדירה",
            "direct hit", "casualties", "damage", "interception",
            "iron dome", "arrow", "david's sling", "debris",
            "fallen rocket", "rocket hit", "missile hit",
            "impact reported", "explosion heard", "siren",
        ]
        self.all_keywords.extend([kw.lower() for kw in extra])
        # Strict Israel-Iran war keywords for filtering interceptions/impacts
        self.strict_keywords = [kw.lower() for kw in STRICT_WAR_KEYWORDS_EN + STRICT_WAR_KEYWORDS_HE]

    # ═══════════════════════════════════════════
    #  PUBLIC: Activation / Trigger
    # ═══════════════════════════════════════════

    async def activate(self, trigger_areas: list[str] = None, reason: str = "siren"):
        """
        Activate full channel monitoring. Called by main.py when a siren fires.

        Args:
            trigger_areas: List of area names from the siren (for context)
            reason: What triggered this ("siren", "manual", "barrage")
        """
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=ACTIVE_WINDOW_MINUTES)

        was_idle = self._mode == "IDLE"
        self._mode = "ACTIVE"
        self._active_until = window_end
        self._activation_count += 1
        self._last_trigger_areas = trigger_areas or []

        if was_idle:
            logger.info(
                f"⚡ TRIGGER: Channel monitor ACTIVATED ({reason}). "
                f"Window: {ACTIVE_WINDOW_MINUTES} min. "
                f"Areas: {', '.join(trigger_areas[:5] if trigger_areas else ['unknown'])}"
            )
            # Scrape recent messages from high-priority channels
            if self.client and self.client.is_connected():
                await self._scrape_recent()
        else:
            logger.info(
                f"⚡ TRIGGER: Window EXTENDED by {ACTIVE_WINDOW_MINUTES} min ({reason}). "
                f"Activation #{self._activation_count}"
            )

    def deactivate(self):
        """Return to idle mode."""
        if self._mode == "ACTIVE":
            logger.info(
                f"💤 Channel monitor → IDLE "
                f"(was active for {self._activation_count} trigger(s))"
            )
            self._mode = "IDLE"
            self._active_until = None

    @property
    def is_active(self) -> bool:
        """Check if the monitoring window is still open."""
        if self._mode != "ACTIVE":
            return False
        if self._active_until and datetime.now(timezone.utc) > self._active_until:
            self.deactivate()
            return False
        return True

    # ═══════════════════════════════════════════
    #  SCRAPE: Fetch recent messages on activation
    # ═══════════════════════════════════════════

    async def _scrape_recent(self):
        """
        When activated, scrape the last N minutes of messages from
        high-priority channels to catch reports posted just before the siren.
        """
        if not self.client:
            return

        lookback = datetime.now(timezone.utc) - timedelta(minutes=SCRAPE_LOOKBACK_MINUTES)
        scraped_messages = []

        for username in TIER2_HIGH_PRIORITY:
            if username not in self._resolved:
                continue
            try:
                entity = await self.client.get_entity(self._resolved[username])
                async for msg in self.client.iter_messages(entity, limit=20):
                    if msg.date and msg.date < lookback:
                        break
                    text = msg.text or msg.raw_text or ""
                    if text and self._is_relevant(text, strict=True):
                        dedup_key = f"{username}:{msg.id}"
                        if dedup_key not in self.seen_ids:
                            self.seen_ids.add(dedup_key)
                            ch_info = MONITORED_CHANNELS.get(username, {})
                            scraped_messages.append(TelegramChannelMessage(
                                text=text,
                                channel_name=ch_info.get("name", username),
                                channel_username=username,
                                message_id=msg.id,
                                timestamp=msg.date or datetime.now(timezone.utc),
                            ))
            except Exception as e:
                logger.warning(f"  Scrape failed for {username}: {e}")

        if scraped_messages:
            scraped_messages.sort(key=lambda m: m.timestamp, reverse=True)
            logger.info(
                f"📡 Scraped {len(scraped_messages)} relevant messages "
                f"from last {SCRAPE_LOOKBACK_MINUTES} min"
            )
            await self.callback(scraped_messages)
        else:
            logger.info(
                f"📡 Scrape complete — no relevant messages "
                f"in last {SCRAPE_LOOKBACK_MINUTES} min"
            )

    # ═══════════════════════════════════════════
    #  MESSAGE HANDLING
    # ═══════════════════════════════════════════

    def _is_relevant(self, text: str, strict: bool = False) -> bool:
        """Check if text is relevant.
        If strict=True, requires both a general keyword AND a strict
        Israel-Iran war keyword (for interceptions/impact reports)."""
        if not text:
            return False
        text_lower = text.lower()
        has_general = any(kw in text_lower for kw in self.all_keywords)
        if not has_general:
            return False
        if strict:
            return any(kw in text_lower for kw in self.strict_keywords)
        return True

    def _get_channel_tier(self, entity_id: int) -> int:
        """Return the tier (1, 2, 3) of a channel by entity ID."""
        if entity_id in self._tier1_ids:
            return 1
        if entity_id in self._tier2_ids:
            return 2
        if entity_id in self._tier3_ids:
            return 3
        return 0

    async def _handle_new_message(self, event):
        """
        Process incoming message based on current mode and channel tier.

        Decision matrix:
        ┌─────────┬─────────────────┬─────────────────┬─────────────────┐
        │  Mode   │ Tier 1 (alerts) │ Tier 2 (news)   │ Tier 3 (extra)  │
        ├─────────┼─────────────────┼─────────────────┼─────────────────┤
        │  IDLE   │ ✅ Process      │ ❌ Ignore       │ ❌ Ignore       │
        │  ACTIVE │ ✅ Process      │ ✅ Process      │ ✅ Process      │
        └─────────┴─────────────────┴─────────────────┴─────────────────┘
        """
        try:
            message = event.message
            text = message.text or message.raw_text or ""
            if not text:
                return

            chat = await event.get_chat()
            entity_id = chat.id
            tier = self._get_channel_tier(entity_id)

            # IDLE mode: only process Tier 1 (alert channels)
            if not self.is_active and tier != 1:
                return

            # Tier 1 (alert channels): general keyword match
            # Tier 2/3 (news/analysis): strict Israel-Iran war filter
            use_strict = tier != 1
            if not self._is_relevant(text, strict=use_strict):
                return

            channel_name = getattr(chat, 'title', 'Unknown')
            channel_username = getattr(chat, 'username', '')

            # Dedup
            dedup_key = f"{channel_username}:{message.id}"
            if dedup_key in self.seen_ids:
                return
            self.seen_ids.add(dedup_key)

            if len(self.seen_ids) > 2000:
                items = list(self.seen_ids)
                self.seen_ids = set(items[len(items) // 2:])

            tg_msg = TelegramChannelMessage(
                text=text,
                channel_name=channel_name,
                channel_username=channel_username,
                message_id=message.id,
                timestamp=message.date or datetime.now(timezone.utc),
            )

            mode_label = "ACTIVE" if self.is_active else "IDLE/T1"
            logger.info(
                f"📨 [{mode_label}|T{tier}] {channel_name}: "
                f"{tg_msg.snippet[:80]}..."
            )

            await self.callback([tg_msg])

        except Exception as e:
            logger.error(f"Error handling Telegram channel message: {e}")

    # ═══════════════════════════════════════════
    #  LIFECYCLE
    # ═══════════════════════════════════════════

    async def start(self):
        """Initialize Telethon client and resolve all channels."""
        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            logger.warning(
                "⚠️ Telegram API credentials not set. "
                "Channel monitoring DISABLED.\n"
                "  Set TELEGRAM_API_ID + TELEGRAM_API_HASH from "
                "https://my.telegram.org\n"
                "  Set TELEGRAM_PHONE to your phone number"
            )
            return

        self._running = True
        logger.info("🟢 Telegram Channel monitor starting (trigger-based)...")

        self.client = TelegramClient(
            'missile_alert_session',
            int(TELEGRAM_API_ID),
            TELEGRAM_API_HASH
        )

        await self.client.start(phone=TELEGRAM_PHONE)
        logger.info("✅ Telegram client connected")

        # Resolve all channel entities
        for ch_username, ch_info in MONITORED_CHANNELS.items():
            try:
                entity = await self.client.get_entity(ch_username)
                eid = entity.id
                self._resolved[ch_username] = eid

                if ch_username in TIER1_ALWAYS_ON:
                    self._tier1_ids.add(eid)
                elif ch_username in TIER2_HIGH_PRIORITY:
                    self._tier2_ids.add(eid)
                elif ch_username in TIER3_SECONDARY:
                    self._tier3_ids.add(eid)

                self._all_ids.add(eid)
                tier = self._get_channel_tier(eid)
                logger.info(f"  ✅ Tier {tier}: {ch_info['name']} ({ch_username})")
            except Exception as e:
                logger.warning(f"  ❌ Could not resolve {ch_username}: {e}")

        if not self._all_ids:
            logger.error("No channels resolved! Check usernames.")
            return

        # Register handler for ALL channels — filtering by mode in handler
        @self.client.on(events.NewMessage(chats=list(self._all_ids)))
        async def handler(event):
            await self._handle_new_message(event)

        logger.info(
            f"🟢 Channels: {len(self._tier1_ids)} always-on, "
            f"{len(self._tier2_ids)} high-priority, "
            f"{len(self._tier3_ids)} secondary"
        )
        logger.info("💤 Starting in IDLE mode — waiting for Pikud HaOref trigger")

    async def _window_watchdog(self):
        """Background task that checks if the active window has expired."""
        while self._running:
            if self._mode == "ACTIVE" and self._active_until:
                remaining = (self._active_until - datetime.now(timezone.utc)).total_seconds()
                if remaining <= 0:
                    self.deactivate()
                elif remaining <= 60:
                    logger.info(f"⏳ Active window closing in {int(remaining)}s")
            await asyncio.sleep(15)

    async def run(self):
        """Main run loop."""
        await self.start()

        if not self.client or not self.client.is_connected():
            return

        watchdog = asyncio.create_task(self._window_watchdog())
        logger.info("🟢 Telegram channel monitor running (trigger-based)")

        try:
            await self.client.run_until_disconnected()
        finally:
            watchdog.cancel()

    async def stop(self):
        """Stop the monitor and disconnect."""
        self._running = False
        if self.client:
            await self.client.disconnect()
        logger.info("🔴 Telegram Channel monitor stopped")
