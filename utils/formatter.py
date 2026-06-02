"""
Telegram Message Formatter
Formats missile alerts and news items into rich Telegram messages.
Bilingual: Arabic + English output.
"""
from datetime import datetime, timezone, timedelta
from config.settings import (
    ALERT_EMOJI, SIREN_EMOJI, MISSILE_EMOJI, IMPACT_EMOJI,
    SHIELD_EMOJI, MAP_EMOJI, NEWS_EMOJI, WARNING_EMOJI, CLOCK_EMOJI,
)


# Israel timezone offset (IST = UTC+2, IDT = UTC+3 during summer)
IST = timedelta(hours=2)
IDT = timedelta(hours=3)


def get_israel_time(utc_dt: datetime = None) -> str:
    """Convert UTC datetime to Israel time string."""
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)
    month = utc_dt.month
    if 3 <= month <= 10:
        israel_dt = utc_dt + IDT
        tz_label = "IDT"
    else:
        israel_dt = utc_dt + IST
        tz_label = "IST"
    return israel_dt.strftime(f"%H:%M:%S {tz_label}  •  %d %b %Y")


def format_siren_alert(alerts) -> str:
    """
    Format Pikud HaOref siren alerts for Telegram (single alert, non-batched).
    Kept for backwards compatibility.
    """
    if not alerts:
        return ""
    return format_batched_alert_summary(alerts)


def format_batched_alert_summary(alerts) -> str:
    """
    Format a batched summary of siren alerts in Arabic + English.
    Called after the 30-second batching window closes.

    Args:
        alerts: List of PikudHaorefAlert objects (accumulated over 30s)

    Returns:
        Formatted bilingual Telegram message (HTML parse mode)
    """
    if not alerts:
        return ""

    now_str = get_israel_time()

    # Collect all unique areas with translations
    # (english, arabic, hebrew) — deduplicated by hebrew name
    seen_areas = {}
    alert_type_label = ""
    for alert in alerts:
        if not alert_type_label:
            alert_type_label = alert.alert_type
        for eng, ar, heb in alert.areas_trilingual:
            if heb not in seen_areas:
                seen_areas[heb] = (eng, ar, heb)

    areas = list(seen_areas.values())
    total = len(areas)

    lines = []

    # ═══ HEADER ═══
    lines.append(f"{SIREN_EMOJI}{SIREN_EMOJI}{SIREN_EMOJI} <b>ALERT / إنذار</b> {SIREN_EMOJI}{SIREN_EMOJI}{SIREN_EMOJI}")
    lines.append("")
    lines.append(f"{CLOCK_EMOJI} <b>{now_str}</b>")
    lines.append("")

    # ═══ ALERT TYPE ═══
    if alert_type_label:
        lines.append(f"<b>{alert_type_label}</b>")
        lines.append("")

    # ═══ SUMMARY LINE ═══
    lines.append(f"<b>{total} location{'s' if total != 1 else ''} under alert</b>")
    lines.append(f"<b>{total} {'مواقع' if total > 1 else 'موقع'} تحت الإنذار</b>")
    lines.append("")

    # ═══ LOCATIONS — ENGLISH ═══
    lines.append(f"<b>Locations:</b>")
    for eng, ar, heb in areas:
        lines.append(f"  {MISSILE_EMOJI} {_escape_html(eng)}")
    lines.append("")

    # ═══ LOCATIONS — ARABIC ═══
    lines.append(f"<b>:المواقع</b>")
    for eng, ar, heb in areas:
        lines.append(f"  {MISSILE_EMOJI} {_escape_html(ar)}")
    lines.append("")

    # ═══ BARRAGE WARNING ═══
    if total > 5:
        lines.append(f"{WARNING_EMOJI} <b>Large barrage — {total} areas / مطر صاروخي كثيف — {total} مناطق</b>")
        lines.append("")

    # ═══ SAFETY MESSAGE ═══
    lines.append(f"{SHIELD_EMOJI} <b>Seek shelter immediately. Stay for 10 minutes.</b>")
    lines.append(f"{SHIELD_EMOJI} <b>احتموا فوراً. ابقوا في الملجأ 10 دقائق.</b>")
    lines.append("")

    # ═══ FOOTER ═══
    lines.append("─" * 30)
    lines.append(f"<i>Source: Pikud HaOref | المصدر: بيكود هعورف</i>")

    return "\n".join(lines)


def format_news_update(news_items) -> str:
    """
    Format news articles about missile impacts for Telegram.
    Bilingual Arabic + English.
    """
    if not news_items:
        return ""

    now_str = get_israel_time()

    lines = []
    lines.append(f"{NEWS_EMOJI} <b>WAR NEWS UPDATE / تحديث أخبار الحرب</b>")
    lines.append(f"{CLOCK_EMOJI} <i>{now_str}</i>")
    lines.append("")

    for i, item in enumerate(news_items[:5], 1):
        lines.append(f"<b>{i}. {_escape_html(item.title)}</b>")
        if item.snippet:
            lines.append(f"<i>{_escape_html(item.snippet[:200])}</i>")
        lines.append(f"📎 <a href=\"{item.link}\">Read more / اقرأ المزيد ({item.source})</a>")
        if item.published:
            lines.append(f"  {CLOCK_EMOJI} {get_israel_time(item.published)}")
        lines.append("")

    if len(news_items) > 5:
        lines.append(f"<i>+ {len(news_items) - 5} more articles / مقالات إضافية</i>")
        lines.append("")

    lines.append("─" * 30)
    lines.append(f"<i>Israel-Iran War Monitor / مراقب حرب إسرائيل-إيران</i>")

    return "\n".join(lines)


def format_impact_report(location: str, details: str, source: str = "") -> str:
    """
    Format a confirmed missile impact report.
    Bilingual Arabic + English.
    """
    now_str = get_israel_time()

    lines = []
    lines.append(f"{IMPACT_EMOJI}{IMPACT_EMOJI} <b>IMPACT REPORT / تقرير إصابة</b> {IMPACT_EMOJI}{IMPACT_EMOJI}")
    lines.append("")
    lines.append(f"{CLOCK_EMOJI} <b>{now_str}</b>")
    lines.append("")
    lines.append(f"{MAP_EMOJI} <b>Location / الموقع:</b> {_escape_html(location)}")
    lines.append(f"📋 <b>Details / التفاصيل:</b> {_escape_html(details)}")
    if source:
        lines.append(f"📎 <b>Source / المصدر:</b> {_escape_html(source)}")
    lines.append("")
    lines.append("─" * 30)
    lines.append(f"<i>Israel-Iran War Monitor / مراقب حرب إسرائيل-إيران</i>")

    return "\n".join(lines)


def format_daily_summary(total_alerts: int, total_areas: int, top_areas: list, news_count: int) -> str:
    """
    Format a daily summary of alert activity.
    Bilingual Arabic + English.
    """
    from config.settings import AREA_TRANSLATIONS

    now_str = get_israel_time()

    lines = []
    lines.append(f"📊 <b>DAILY SUMMARY / ملخص يومي</b>")
    lines.append(f"{CLOCK_EMOJI} <i>{now_str}</i>")
    lines.append("")
    lines.append(f"  {SIREN_EMOJI} Alert events / أحداث إنذار: <b>{total_alerts}</b>")
    lines.append(f"  {MAP_EMOJI} Areas affected / مناطق متأثرة: <b>{total_areas}</b>")
    lines.append(f"  {NEWS_EMOJI} News articles / مقالات إخبارية: <b>{news_count}</b>")
    lines.append("")

    if top_areas:
        lines.append("<b>Most targeted / الأكثر استهدافاً:</b>")
        for area, count in top_areas[:10]:
            bar = "█" * min(count, 20)
            entry = AREA_TRANSLATIONS.get(area)
            if entry and isinstance(entry, tuple):
                eng, ar = entry[0], entry[1]
                lines.append(f"  {eng} / {ar}: {bar} ({count})")
            else:
                lines.append(f"  {area}: {bar} ({count})")
        lines.append("")

    lines.append("─" * 30)
    lines.append(f"<i>Israel-Iran War Monitor / مراقب حرب إسرائيل-إيران</i>")

    return "\n".join(lines)


def format_status_message(status: str) -> str:
    """Format a bot status message (startup, shutdown, errors)."""
    now_str = get_israel_time()
    return (
        f"🤖 <b>Bot Status</b>\n"
        f"{CLOCK_EMOJI} {now_str}\n\n"
        f"{status}"
    )


def format_telegram_channel_update(messages) -> str:
    """
    Format messages from monitored Israeli Telegram channels.
    Bilingual Arabic + English.
    """
    if not messages:
        return ""

    now_str = get_israel_time()

    lines = []
    lines.append(f"📡 <b>CHANNEL REPORT / تقرير القنوات</b>")
    lines.append(f"{CLOCK_EMOJI} <i>{now_str}</i>")
    lines.append("")

    for i, msg in enumerate(messages[:5], 1):
        source_label = _escape_html(msg.channel_name)
        lines.append(f"<b>{i}. [{source_label}]</b>")
        lines.append(f"<i>{_escape_html(msg.snippet[:300])}</i>")
        if msg.link:
            lines.append(f"📎 <a href=\"{msg.link}\">View / عرض</a>")
        if msg.timestamp:
            lines.append(f"  {CLOCK_EMOJI} {get_israel_time(msg.timestamp)}")
        lines.append("")

    if len(messages) > 5:
        lines.append(f"<i>+ {len(messages) - 5} more / المزيد</i>")
        lines.append("")

    lines.append("─" * 30)
    lines.append(f"<i>Israel-Iran War Monitor / مراقب حرب إسرائيل-إيران</i>")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
