"""
Standalone missile alert monitor that uses curl for HTTP requests.
Designed to run in environments where Python DNS resolution is unavailable.
"""
import asyncio
import json
import subprocess
import logging
import sys
from datetime import datetime, timezone, timedelta
from config.settings import (
    PIKUD_HAOREF_URL,
    PIKUD_HAOREF_HEADERS,
    PIKUD_HAOREF_POLL_INTERVAL,
    NEWS_RSS_POLL_INTERVAL,
    AREA_TRANSLATIONS,
    ALERT_KEYWORDS_EN,
    ALERT_KEYWORDS_HE,
    NEWS_RSS_FEEDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    SIREN_EMOJI,
    MISSILE_EMOJI,
    WARNING_EMOJI,
    SHIELD_EMOJI,
    CLOCK_EMOJI,
    NEWS_EMOJI,
    MAP_EMOJI,
    IMPACT_EMOJI,
)
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("monitor")

# Israel timezone
IDT = timedelta(hours=3)
IST = timedelta(hours=2)


def get_israel_time() -> str:
    utc_dt = datetime.now(timezone.utc)
    month = utc_dt.month
    if 3 <= month <= 10:
        israel_dt = utc_dt + IDT
        tz_label = "IDT"
    else:
        israel_dt = utc_dt + IST
        tz_label = "IST"
    return israel_dt.strftime(f"%H:%M:%S {tz_label}  •  %d %b %Y")


def curl_get(url: str, headers: dict = None, timeout: int = 10) -> str:
    """HTTP GET using curl subprocess."""
    cmd = ["curl", "-s", "-m", str(timeout)]
    if headers:
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
    cmd.append(url)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return result.stdout
    except Exception as e:
        logger.error(f"curl GET failed: {e}")
        return ""


def curl_post_json(url: str, data: dict, timeout: int = 15) -> dict:
    """HTTP POST JSON using curl subprocess."""
    cmd = [
        "curl", "-s", "-m", str(timeout),
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(data),
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if result.stdout:
            return json.loads(result.stdout)
        return {}
    except Exception as e:
        logger.error(f"curl POST failed: {e}")
        return {}


def send_telegram(text: str, disable_notification: bool = False) -> bool:
    """Send a message to the Telegram channel."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": disable_notification,
    }
    resp = curl_post_json(url, payload)
    if resp.get("ok"):
        logger.info(f"Message sent to {TELEGRAM_CHANNEL_ID}")
        return True
    else:
        logger.error(f"Telegram send failed: {resp.get('description', 'unknown error')}")
        return False


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def translate_area(area: str) -> str:
    eng = AREA_TRANSLATIONS.get(area)
    if eng:
        return f"{eng} ({area})"
    return area


def format_alert(alerts_data: list, falls: int = 0, interceptions: int = 0) -> str:
    """Format siren alerts for Telegram."""
    now_str = get_israel_time()
    lines = [
        f"{SIREN_EMOJI}{SIREN_EMOJI}{SIREN_EMOJI} <b>RED ALERT — INCOMING THREAT</b> {SIREN_EMOJI}{SIREN_EMOJI}{SIREN_EMOJI}",
        "",
        f"{CLOCK_EMOJI} <b>{now_str}</b>",
        "",
    ]

    total_areas = 0
    for alert in alerts_data:
        cat = str(alert.get("cat", ""))
        title = alert.get("title", "")
        data = alert.get("data", [])
        if isinstance(data, str):
            data = [data]

        cat_map = {
            "1": "🚀 Rocket / Missile Alert",
            "2": "🚀 Rocket / Missile Alert",
            "3": "⚠️ Earthquake Alert",
            "6": "🛩️ Hostile Aircraft Intrusion",
            "13": "⚠️ Terror Infiltration",
        }
        alert_type = cat_map.get(cat, f"⚠️ Alert (Category {cat})")
        lines.append(f"<b>{alert_type}</b>")
        if title:
            lines.append(f"<i>{title}</i>")
        lines.append("")

        areas = [translate_area(a) for a in data]
        total_areas += len(areas)

        if len(areas) <= 10:
            for area in areas:
                lines.append(f"  {MISSILE_EMOJI} {area}")
        else:
            for area in areas[:8]:
                lines.append(f"  {MISSILE_EMOJI} {area}")
            lines.append(f"  ... and <b>{len(areas) - 8} more areas</b>")
        lines.append("")

    if total_areas > 5:
        lines.append(f"{WARNING_EMOJI} <b>Large-scale barrage — {total_areas} areas under alert</b>")
        lines.append("")

    lines.append(f"{SHIELD_EMOJI} <b>Seek shelter immediately. Stay in protected space for 10 minutes.</b>")
    lines.append("")
    if falls > 0 or interceptions > 0:
        lines.append(f"📊 <b>Today:</b> {IMPACT_EMOJI} {falls} fall(s)  |  🛡️ {interceptions} interception(s)")
        lines.append("")
    lines.append("─" * 30)
    lines.append("<i>Source: Pikud HaOref (Home Front Command)</i>")

    return "\n".join(lines)


def format_news(items: list, falls: int, interceptions: int) -> str:
    """Format RSS news items for Telegram with fall/interception counters."""
    now_str = get_israel_time()
    lines = [
        f"{NEWS_EMOJI} <b>MISSILE NEWS UPDATE</b>",
        f"{CLOCK_EMOJI} <i>{now_str}</i>",
        "",
        f"{IMPACT_EMOJI} Falls: <b>{falls}</b>  |  🛡️ Interceptions: <b>{interceptions}</b>",
        "",
    ]
    for i, item in enumerate(items[:5], 1):
        title = escape_html(item.get("title", ""))
        link = item.get("link", "")
        source = item.get("source", "")
        snippet = escape_html(item.get("snippet", "")[:200])
        lines.append(f"<b>{i}. {title}</b>")
        if snippet:
            lines.append(f"<i>{snippet}</i>")
        if link:
            lines.append(f"📎 <a href=\"{link}\">Read more ({source})</a>")
        lines.append("")

    lines.append("─" * 30)
    lines.append("<i>🤖 Israeli media monitor</i>")
    return "\n".join(lines)


class MissileAlertMonitor:
    """Main monitor using curl for all HTTP. News only triggers after siren alerts."""

    # How long after a siren to keep polling news for impact reports
    NEWS_WINDOW_MINUTES = 20
    NEWS_POLL_INTERVAL = 30  # Poll news every 30s during active window

    # Keywords that indicate a fall/impact
    FALL_KEYWORDS = [
        "fall", "fallen", "fell", "impact", "hit", "struck", "landed",
        "נפילה", "נפילות", "פגיעה", "פגיעות", "נפל",
    ]
    # Keywords that indicate an interception
    INTERCEPTION_KEYWORDS = [
        "intercept", "intercepted", "interception", "iron dome", "shot down",
        "יירוט", "יורט", "כיפת ברזל", "הופל",
    ]

    def __init__(self):
        self.seen_alerts: set = set()
        self.seen_news: set = set()
        self.alert_count = 0
        self.news_count = 0
        self.fall_count = 0
        self.interception_count = 0
        self._last_siren_time: datetime | None = None  # When last siren was detected

    @property
    def _news_window_active(self) -> bool:
        """True if we're within the news-fetch window after a siren."""
        if self._last_siren_time is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self._last_siren_time).total_seconds()
        return elapsed < self.NEWS_WINDOW_MINUTES * 60

    def _dedup_key(self, alert: dict) -> str:
        data = alert.get("data", [])
        if isinstance(data, str):
            data = [data]
        areas = "|".join(sorted(data))
        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        return f"{alert.get('cat', '')}:{areas}:{now}"

    async def poll_pikud_haoref(self):
        """Poll Pikud HaOref for siren alerts."""
        text = curl_get(PIKUD_HAOREF_URL, headers=PIKUD_HAOREF_HEADERS)
        text = text.strip()

        if not text or text == "null":
            return

        if text.startswith('\ufeff'):
            text = text[1:]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return

        new_alerts = []
        for alert in data:
            key = self._dedup_key(alert)
            if key not in self.seen_alerts:
                self.seen_alerts.add(key)
                new_alerts.append(alert)

        # Trim dedup set
        if len(self.seen_alerts) > 1000:
            items = list(self.seen_alerts)
            self.seen_alerts = set(items[len(items) // 2:])

        if new_alerts:
            self.alert_count += len(new_alerts)
            self._last_siren_time = datetime.now(timezone.utc)
            logger.info(f"🚨 NEW SIREN ALERT! {len(new_alerts)} alert(s) — news window activated for {self.NEWS_WINDOW_MINUTES}min")
            msg = format_alert(new_alerts, self.fall_count, self.interception_count)
            send_telegram(msg, disable_notification=False)

    async def poll_news_rss(self):
        """Poll Israeli news RSS feeds for missile impact reports."""
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not available, skipping RSS")
            return

        all_keywords = [kw.lower() for kw in ALERT_KEYWORDS_EN] + ALERT_KEYWORDS_HE

        new_items = []
        for source_name, feed_url in NEWS_RSS_FEEDS.items():
            try:
                raw = curl_get(feed_url, timeout=15)
                if not raw:
                    continue
                feed = feedparser.parse(raw)
                for entry in feed.entries[:10]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    link = entry.get("link", "")
                    combined = (title + " " + summary).lower()

                    if not any(kw in combined for kw in all_keywords):
                        continue

                    if link in self.seen_news:
                        continue
                    self.seen_news.add(link)

                    new_items.append({
                        "title": title,
                        "snippet": summary,
                        "link": link,
                        "source": source_name,
                    })
            except Exception as e:
                logger.error(f"Error parsing {source_name}: {e}")

        # Trim dedup set
        if len(self.seen_news) > 500:
            items = list(self.seen_news)
            self.seen_news = set(items[len(items) // 2:])

        if new_items:
            # Count falls and interceptions from article text
            for item in new_items:
                text_lower = (item.get("title", "") + " " + item.get("snippet", "")).lower()
                if any(kw in text_lower for kw in self.FALL_KEYWORDS):
                    self.fall_count += 1
                if any(kw in text_lower for kw in self.INTERCEPTION_KEYWORDS):
                    self.interception_count += 1

            self.news_count += len(new_items)
            logger.info(f"📰 {len(new_items)} new article(s) | Falls: {self.fall_count} | Interceptions: {self.interception_count}")
            msg = format_news(new_items, self.fall_count, self.interception_count)
            send_telegram(msg, disable_notification=True)

    async def pikud_loop(self):
        """Continuously poll Pikud HaOref every 3 seconds."""
        logger.info("🟢 Pikud HaOref monitor started (polling every 3s)")
        while True:
            try:
                await self.poll_pikud_haoref()
            except Exception as e:
                logger.error(f"Pikud HaOref poll error: {e}")
            await asyncio.sleep(PIKUD_HAOREF_POLL_INTERVAL)

    async def news_loop(self):
        """Poll news RSS only when triggered by a siren alert."""
        logger.info("🟢 News monitor started (siren-triggered only)")
        while True:
            if self._news_window_active:
                try:
                    remaining = self.NEWS_WINDOW_MINUTES * 60 - (
                        datetime.now(timezone.utc) - self._last_siren_time
                    ).total_seconds()
                    logger.info(f"📰 News window active ({remaining:.0f}s remaining), polling RSS...")
                    await self.poll_news_rss()
                except Exception as e:
                    logger.error(f"News poll error: {e}")
                await asyncio.sleep(self.NEWS_POLL_INTERVAL)
            else:
                # Idle — check every 5s if a siren has activated the window
                await asyncio.sleep(5)

    async def status_loop(self):
        """Log periodic status every 5 minutes."""
        while True:
            await asyncio.sleep(300)
            window_status = "ACTIVE" if self._news_window_active else "idle"
            logger.info(
                f"📊 Status: {self.alert_count} alerts, {self.news_count} news | "
                f"💥 {self.fall_count} falls, 🛡️ {self.interception_count} interceptions | "
                f"news window: {window_status}"
            )

    async def run(self):
        """Start all monitoring tasks."""
        logger.info("=" * 60)
        logger.info("🚀 Missile Alert Monitor starting...")
        logger.info("=" * 60)

        # Test connection
        logger.info("Testing Telegram connection...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        resp_text = curl_get(url)
        if not resp_text:
            logger.critical("Cannot reach Telegram API!")
            sys.exit(1)
        resp = json.loads(resp_text)
        if not resp.get("ok"):
            logger.critical("Invalid bot token!")
            sys.exit(1)
        bot_name = resp["result"]["username"]
        logger.info(f"✅ Connected as @{bot_name}")

        # Send startup message
        send_telegram(
            f"🤖 <b>Bot Status</b>\n"
            f"{CLOCK_EMOJI} {get_israel_time()}\n\n"
            f"🟢 <b>Bot started successfully</b>\n\n"
            f"Monitoring:\n"
            f"• Pikud HaOref (real-time alerts) — every 3s\n"
            f"• Israeli news feeds — triggered by siren alerts ({self.NEWS_WINDOW_MINUTES}min window)\n\n"
            f"Alerts will be posted automatically.",
            disable_notification=True,
        )

        # Run all loops concurrently
        await asyncio.gather(
            self.pikud_loop(),
            self.news_loop(),
            self.status_loop(),
        )


if __name__ == "__main__":
    monitor = MissileAlertMonitor()
    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
        send_telegram(
            f"🤖 <b>Bot Status</b>\n{CLOCK_EMOJI} {get_israel_time()}\n\n🔴 <b>Bot shutting down</b>",
            disable_notification=True,
        )
