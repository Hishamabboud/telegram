"""
Telegram Message Formatter
Formats missile alerts and news items into rich Telegram messages.
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
    # Simplified — use +3 (IDT) during summer, +2 (IST) otherwise
    # For production, use pytz or zoneinfo
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
    Format Pikud HaOref siren alerts for Telegram.
    
    Args:
        alerts: List of PikudHaorefAlert objects
    
    Returns:
        Formatted Telegram message string (HTML parse mode)
    """
    if not alerts:
        return ""

    now_str = get_israel_time()

    # Group alerts by type
    lines = []
    lines.append(f"{SIREN_EMOJI}{SIREN_EMOJI}{SIREN_EMOJI} <b>RED ALERT — INCOMING THREAT</b> {SIREN_EMOJI}{SIREN_EMOJI}{SIREN_EMOJI}")
    lines.append("")
    lines.append(f"{CLOCK_EMOJI} <b>{now_str}</b>")
    lines.append("")

    total_areas = 0
    for alert in alerts:
        lines.append(f"<b>{alert.alert_type}</b>")
        if alert.title:
            lines.append(f"<i>{alert.title}</i>")
        lines.append("")

        areas_en = alert.areas_english
        total_areas += len(areas_en)

        if len(areas_en) <= 10:
            for area in areas_en:
                lines.append(f"  {MISSILE_EMOJI} {area}")
        else:
            # For large barrages, group and summarize
            for area in areas_en[:8]:
                lines.append(f"  {MISSILE_EMOJI} {area}")
            lines.append(f"  ... and <b>{len(areas_en) - 8} more areas</b>")
        lines.append("")

    if total_areas > 5:
        lines.append(f"{WARNING_EMOJI} <b>Large-scale barrage — {total_areas} areas under alert</b>")
        lines.append("")

    lines.append(f"{SHIELD_EMOJI} <b>Seek shelter immediately. Stay in protected space for 10 minutes.</b>")
    lines.append("")
    lines.append("─" * 30)
    lines.append(f"<i>Source: Pikud HaOref (Home Front Command)</i>")
    lines.append(f"<i>🤖 Automated alert • @YourChannelName</i>")

    return "\n".join(lines)


def format_news_update(news_items) -> str:
    """
    Format news articles about missile impacts for Telegram.
    
    Args:
        news_items: List of NewsItem objects
    
    Returns:
        Formatted Telegram message string (HTML parse mode)
    """
    if not news_items:
        return ""

    now_str = get_israel_time()

    lines = []
    lines.append(f"{NEWS_EMOJI} <b>MISSILE NEWS UPDATE</b>")
    lines.append(f"{CLOCK_EMOJI} <i>{now_str}</i>")
    lines.append("")

    for i, item in enumerate(news_items[:5], 1):  # Max 5 items per message
        lines.append(f"<b>{i}. {_escape_html(item.title)}</b>")
        if item.snippet:
            lines.append(f"<i>{_escape_html(item.snippet[:200])}</i>")
        lines.append(f"📎 <a href=\"{item.link}\">Read more ({item.source})</a>")
        if item.published:
            lines.append(f"  {CLOCK_EMOJI} {get_israel_time(item.published)}")
        lines.append("")

    if len(news_items) > 5:
        lines.append(f"<i>+ {len(news_items) - 5} more articles</i>")
        lines.append("")

    lines.append("─" * 30)
    lines.append(f"<i>🤖 Israeli media monitor • @YourChannelName</i>")

    return "\n".join(lines)


def format_impact_report(location: str, details: str, source: str = "") -> str:
    """
    Format a confirmed missile impact report.
    
    Args:
        location: City/area of impact
        details: Description of what happened
        source: News source
    
    Returns:
        Formatted Telegram message (HTML)
    """
    now_str = get_israel_time()

    lines = []
    lines.append(f"{IMPACT_EMOJI}{IMPACT_EMOJI} <b>CONFIRMED IMPACT REPORT</b> {IMPACT_EMOJI}{IMPACT_EMOJI}")
    lines.append("")
    lines.append(f"{CLOCK_EMOJI} <b>{now_str}</b>")
    lines.append("")
    lines.append(f"{MAP_EMOJI} <b>Location:</b> {_escape_html(location)}")
    lines.append(f"📋 <b>Details:</b> {_escape_html(details)}")
    if source:
        lines.append(f"📎 <b>Source:</b> {_escape_html(source)}")
    lines.append("")
    lines.append("─" * 30)
    lines.append(f"<i>🤖 Automated report • @YourChannelName</i>")

    return "\n".join(lines)


def format_daily_summary(total_alerts: int, total_areas: int, top_areas: list, news_count: int) -> str:
    """
    Format a daily summary of alert activity.
    
    Args:
        total_alerts: Number of alert events today
        total_areas: Total areas that received alerts
        top_areas: List of (area_name, count) tuples
        news_count: Number of related news articles
    
    Returns:
        Formatted Telegram message (HTML)
    """
    now_str = get_israel_time()

    lines = []
    lines.append(f"📊 <b>DAILY ALERT SUMMARY</b>")
    lines.append(f"{CLOCK_EMOJI} <i>{now_str}</i>")
    lines.append("")
    lines.append(f"  {SIREN_EMOJI} Total alert events: <b>{total_alerts}</b>")
    lines.append(f"  {MAP_EMOJI} Areas affected: <b>{total_areas}</b>")
    lines.append(f"  {NEWS_EMOJI} Related news articles: <b>{news_count}</b>")
    lines.append("")

    if top_areas:
        lines.append("<b>Most targeted areas:</b>")
        for area, count in top_areas[:10]:
            bar = "█" * min(count, 20)
            lines.append(f"  {area}: {bar} ({count})")
        lines.append("")

    lines.append("─" * 30)
    lines.append(f"<i>🤖 Daily summary • @YourChannelName</i>")

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

    Args:
        messages: List of TelegramChannelMessage objects

    Returns:
        Formatted Telegram message string (HTML parse mode)
    """
    if not messages:
        return ""

    now_str = get_israel_time()

    lines = []
    lines.append(f"📡 <b>TELEGRAM CHANNEL REPORT</b>")
    lines.append(f"{CLOCK_EMOJI} <i>{now_str}</i>")
    lines.append("")

    for i, msg in enumerate(messages[:5], 1):
        source_label = _escape_html(msg.channel_name)
        lines.append(f"<b>{i}. [{source_label}]</b>")
        lines.append(f"<i>{_escape_html(msg.snippet[:300])}</i>")
        if msg.link:
            lines.append(f"📎 <a href=\"{msg.link}\">View original</a>")
        if msg.timestamp:
            lines.append(f"  {CLOCK_EMOJI} {get_israel_time(msg.timestamp)}")
        lines.append("")

    if len(messages) > 5:
        lines.append(f"<i>+ {len(messages) - 5} more messages</i>")
        lines.append("")

    lines.append("─" * 30)
    lines.append(f"<i>📡 Israeli Telegram channels • @YourChannelName</i>")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
