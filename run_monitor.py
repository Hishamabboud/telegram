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


# Hebrew → (English, Arabic) area translations
AREA_TRANSLATIONS_AR = {
    "תל אביב - מרכז העיר": "تل أبيب",
    "תל אביב - דרום העיר": "تل أبيب",
    "תל אביב - צפון הישן": "تل أبيب",
    "חיפה - כרמל ועיר תחתית": "حيفا",
    "חיפה - מערב": "حيفا",
    "חיפה - נווה שאנן": "حيفا",
    "ירושלים - מרכז": "القدس",
    "באר שבע": "بئر السبع",
    "אשדוד": "أسدود",
    "אשקלון": "عسقلان",
    "שדרות": "سديروت",
    "נתיבות": "نتيفوت",
    "אופקים": "أوفاكيم",
    "קריית שמונה": "كريات شمونا",
    "נהריה": "نهاريا",
    "עכו": "عكا",
    "כרמיאל": "كرميئيل",
    "צפת": "صفد",
    "טבריה": "طبريا",
    "עפולה": "العفولة",
    "מגדל העמק": "مجدال هعيمق",
    "נצרת": "الناصرة",
    "חדרה": "الخضيرة",
    "נתניה": "نتانيا",
    "הרצליה": "هرتسليا",
    "פתח תקווה": "بيتح تكفا",
    "ראשון לציון": "ريشون لتسيون",
    "רחובות": "رحوفوت",
    "לוד": "اللد",
    "רמלה": "الرملة",
    "מודיעין": "موديعين",
    "בית שמש": "بيت شيمش",
    "דימונה": "ديمونا",
    "אילת": "إيلات",
    "קריית גת": "كريات جات",
    "מטולה": "متولا",
    "מנרה": "منارة",
    "מרגליות": "مرجليوت",
    "בית ג'אן": "بيت جن",
    "חורפיש": "حرفيش",
}


def translate_area(area: str) -> str:
    eng = AREA_TRANSLATIONS.get(area, "")
    ar = AREA_TRANSLATIONS_AR.get(area, "")
    if eng and ar:
        return f"{eng} / {ar}"
    elif eng:
        return eng
    elif ar:
        return f"{area} / {ar}"
    return area


def format_alert(alerts_data: list, falls: int = 0, interceptions: int = 0) -> str:
    """Format siren alerts for Telegram — bilingual English/Arabic."""
    now_str = get_israel_time()

    # Determine alert type
    cat = str(alerts_data[0].get("cat", "")) if alerts_data else ""
    cat_map = {
        "0": ("🚀 Rockets / صواريخ", "🚀"),
        "1": ("🚀 Rockets / صواريخ", "🚀"),
        "2": ("🚀 Rockets / صواريخ", "🚀"),
        "3": ("⚠️ Earthquake / زلزال", "⚠️"),
        "6": ("🛩️ Hostile Aircraft / طائرة معادية", "🛩️"),
        "13": ("⚠️ Infiltration / تسلل", "⚠️"),
    }
    alert_label, icon = cat_map.get(cat, ("🚀 Rockets / صواريخ", "🚀"))

    # Collect all areas
    all_areas = []
    for alert in alerts_data:
        data = alert.get("data", [])
        if isinstance(data, str):
            data = [data]
        all_areas.extend(data)

    lines = [
        f"🔴 <b>{alert_label}</b>",
        f"{CLOCK_EMOJI} {now_str}",
    ]

    for area in all_areas[:15]:
        lines.append(f"  {icon} {translate_area(area)}")
    if len(all_areas) > 15:
        lines.append(f"  +<b>{len(all_areas) - 15}</b> more / أخرى")

    if falls > 0 or interceptions > 0:
        lines.append(f"💥{falls} 🛡️{interceptions}")

    return "\n".join(lines)


def format_news(items: list, falls: int, interceptions: int) -> str:
    """Format RSS news items for Telegram — bilingual English/Arabic."""
    now_str = get_israel_time()
    lines = [
        f"{NEWS_EMOJI} <b>Impact Report / تقرير سقوط</b>",
        f"{CLOCK_EMOJI} <i>{now_str}</i>",
        "",
        f"{IMPACT_EMOJI} Falls / سقوط: <b>{falls}</b>  |  🛡️ Interceptions / اعتراضات: <b>{interceptions}</b>",
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
            lines.append(f"📎 <a href=\"{link}\">Read more / اقرأ المزيد ({source})</a>")
        lines.append("")

    lines.append("─" * 30)
    lines.append("<i>🤖 Israeli media / إعلام إسرائيلي</i>")
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
        """Poll for siren alerts — tries Pikud HaOref first, falls back to Tzofar API."""
        # Try Pikud HaOref first
        text = curl_get(PIKUD_HAOREF_URL, headers=PIKUD_HAOREF_HEADERS)
        text = text.strip()

        # If blocked (Access Denied / HTML response), try Tzofar API
        if not text or text == "null" or text.startswith("<"):
            text = curl_get("https://api.tzevaadom.co.il/notifications")
            text = text.strip()
            if not text or text == "[]":
                return
            # Tzofar returns a list of alert objects
            try:
                tzofar_data = json.loads(text)
            except json.JSONDecodeError:
                return
            if not tzofar_data:
                return
            # Convert Tzofar format to standard format
            data = []
            for item in tzofar_data:
                data.append({
                    "id": item.get("notificationId", ""),
                    "cat": item.get("threat", 1),
                    "title": item.get("title", ""),
                    "data": item.get("cities", []),
                })
        else:
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

    # Only match articles about actual falls, impacts, interceptions, damage
    IMPACT_NEWS_KEYWORDS = [
        # English — falls/impacts
        "fall", "fallen", "fell", "impact", "hit", "hits", "struck", "landed",
        "direct hit", "shrapnel", "crater", "damage", "damaged",
        # English — interceptions
        "intercept", "intercepted", "interception", "iron dome", "shot down",
        "air defense", "air defence",
        # English — casualties from rockets
        "wounded in rocket", "injured in rocket", "killed in rocket",
        "wounded in missile", "injured in missile",
        # Hebrew — falls/impacts
        "נפילה", "נפילות", "נפל", "פגיעה", "פגיעות", "פגיעה ישירה",
        "שברים", "נזק", "רסיסים",
        # Hebrew — interceptions
        "יירוט", "יורט", "כיפת ברזל",
        # Arabic — falls/impacts
        "سقوط", "سقطت", "إصابة مباشرة", "أضرار", "شظايا",
        # Arabic — interceptions
        "اعتراض", "القبة الحديدية",
    ]

    async def poll_news_rss(self):
        """Poll Israeli news RSS feeds for fall/interception reports only."""
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not available, skipping RSS")
            return

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

                    # Only match fall/impact/interception articles
                    if not any(kw in combined for kw in self.IMPACT_NEWS_KEYWORDS):
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
            f"🤖 <b>Bot Status / حالة البوت</b>\n"
            f"{CLOCK_EMOJI} {get_israel_time()}\n\n"
            f"🟢 <b>Bot started / البوت يعمل</b>\n\n"
            f"• Pikud HaOref alerts every 3s / إنذارات بيكود هعورف كل 3 ثوانٍ\n"
            f"• News after sirens ({self.NEWS_WINDOW_MINUTES}min) / أخبار بعد الإنذار ({self.NEWS_WINDOW_MINUTES} دقيقة)\n\n"
            f"Alerts posted automatically / الإنذارات تُنشر تلقائياً",
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
