"""
Configuration settings for the Missile Alert Telegram Bot.
All sensitive values are loaded from environment variables.
"""
import os

# ─── Telegram Configuration ───
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")  # e.g. "@your_channel_name" or "-100xxxxxxxxxx"

# ─── Telethon (Telegram User API) — for monitoring channels ───
# Get these from https://my.telegram.org/apps
TELEGRAM_API_ID = os.environ.get("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.environ.get("TELEGRAM_PHONE", "")  # Your phone number e.g. "+31612345678"

# ─── Polling Intervals (seconds) ───
PIKUD_HAOREF_POLL_INTERVAL = 3       # Home Front Command alerts (fast polling)
NEWS_RSS_POLL_INTERVAL = 60           # RSS news feeds
MEDIA_SCRAPE_POLL_INTERVAL = 120      # Web scraping fallback

# ─── Telegram Channel Trigger Settings ───
ACTIVE_WINDOW_MINUTES = 10   # How long to monitor all channels after a siren
SCRAPE_LOOKBACK_MINUTES = 5  # How far back to scrape when activated

# ─── Alert Sources ───
# Pikud HaOref (Home Front Command) — real-time rocket alert API
PIKUD_HAOREF_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
PIKUD_HAOREF_HISTORY_URL = "https://www.oref.org.il/WarningMessages/alert/History/AlertsHistory.json"

# Headers required by the Pikud HaOref API
PIKUD_HAOREF_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ─── Israeli News RSS Feeds ───
NEWS_RSS_FEEDS = {
    "Ynet (English)":  "https://www.ynetnews.com/category/3089",
    "Times of Israel":  "https://www.timesofisrael.com/feed/",
    "Jerusalem Post":  "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
    "i24 News":  "https://www.i24news.tv/en/rss",
    "Kan News":  "https://www.kan.org.il/lobby/kan-news/",
}

# ─── Keywords for filtering missile/rocket news ───
ALERT_KEYWORDS_EN = [
    "rocket", "missile", "interception", "iron dome", "siren",
    "red alert", "barrage", "projectile", "mortar", "drone",
    "ballistic", "shrapnel", "impact", "fallen", "explosion",
    "rocket fire", "rocket attack", "missile attack", "uav",
    "cruise missile", "air raid", "shelter", "tzeva adom"
]

ALERT_KEYWORDS_HE = [
    "רקטה", "טיל", "יירוט", "כיפת ברזל", "צבע אדום",
    "אזעקה", "מטח", "פגיעה", "שיגור", "ירי", "נפילה",
    "מרגמה", "כטב\"מ", "רחפן", "מפץ", "פיצוץ",
    "התקפת טילים", "ירי רקטות", "בליסטי"
]

# ─── City / Region mappings (Pikud HaOref area codes → readable names) ───
# This maps the Hebrew area names from the alert system to English
AREA_TRANSLATIONS = {
    "תל אביב - מרכז העיר": "Tel Aviv - City Center",
    "תל אביב - דרום העיר": "Tel Aviv - South",
    "תל אביב - צפון הישן": "Tel Aviv - North (Old)",
    "חיפה - כרמל ועיר תחתית": "Haifa - Carmel & Downtown",
    "חיפה - מערב": "Haifa - West",
    "חיפה - נווה שאנן": "Haifa - Neve Sha'anan",
    "ירושלים - מרכז": "Jerusalem - Center",
    "באר שבע": "Be'er Sheva",
    "אשדוד": "Ashdod",
    "אשקלון": "Ashkelon",
    "שדרות": "Sderot",
    "נתיבות": "Netivot",
    "אופקים": "Ofakim",
    "קריית שמונה": "Kiryat Shmona",
    "נהריה": "Nahariya",
    "עכו": "Akko",
    "כרמיאל": "Karmiel",
    "צפת": "Safed (Tzfat)",
    "טבריה": "Tiberias",
    "עפולה": "Afula",
    "מגדל העמק": "Migdal HaEmek",
    "נצרת": "Nazareth",
    "חדרה": "Hadera",
    "נתניה": "Netanya",
    "הרצליה": "Herzliya",
    "רעננה": "Ra'anana",
    "פתח תקווה": "Petah Tikva",
    "ראשון לציון": "Rishon LeZion",
    "רחובות": "Rehovot",
    "לוד": "Lod",
    "רמלה": "Ramla",
    "מודיעין": "Modi'in",
    "בית שמש": "Beit Shemesh",
    "דימונה": "Dimona",
    "ערד": "Arad",
    "אילת": "Eilat",
    "יבנה": "Yavne",
    "גדרה": "Gedera",
    "קריית גת": "Kiryat Gat",
    "קריית מלאכי": "Kiryat Malachi",
}

# ─── Telegram Message Formatting ───
ALERT_EMOJI = "🚨"
SIREN_EMOJI = "🔴"
MISSILE_EMOJI = "🚀"
IMPACT_EMOJI = "💥"
SHIELD_EMOJI = "🛡️"
MAP_EMOJI = "🗺️"
NEWS_EMOJI = "📰"
WARNING_EMOJI = "⚠️"
CLOCK_EMOJI = "🕐"

# ─── Deduplication ───
DEDUP_WINDOW_SECONDS = 300  # 5-minute deduplication window
MAX_HISTORY_SIZE = 500      # Max alerts to keep in memory for dedup

# ─── Logging ───
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = "bot.log"

# ─── Monitored Israeli Telegram Channels ───
# These are public channels the bot listens to for missile/rocket news.
# Uses Telethon (user API), NOT the Bot API.
# Key = channel username (without @), Value = metadata
MONITORED_CHANNELS = {

    # ══════════════════════════════════════════
    #  TIER 1 — ALWAYS-ON ALERT CHANNELS
    #  (Active even in IDLE mode)
    # ══════════════════════════════════════════

    "tzevaadom": {
        "name": "צופר — Tzofar (Red Alert Hebrew)",
        "lang": "he", "type": "alert",
        "description": "Real-time Pikud HaOref siren alerts in Hebrew with maps",
    },
    "tzevaadom_en": {
        "name": "Tzofar — Red Alert (English)",
        "lang": "en", "type": "alert",
        "description": "English translation of Pikud HaOref siren alerts",
    },
    "CumtaAlertsChannel": {
        "name": "Cumta — Red Alerts (Hebrew)",
        "lang": "he", "type": "alert",
    },
    "CumtaAlertsEnglishChannel": {
        "name": "Cumta — Red Alerts (English)",
        "lang": "en", "type": "alert",
    },

    # ══════════════════════════════════════════
    #  TIER 2 — HIGH-PRIORITY NEWS
    #  (Scraped on activation + live during window)
    # ══════════════════════════════════════════

    # ── Unofficial / Independent — Top Israeli channels ──

    "abualiexpress": {
        "name": "אבו עלי אקספרס — Abu Ali Express",
        "lang": "he", "type": "news",
        "followers": "568K+",
        "description": "Israel's #2 channel. Arab affairs, security, rockets. Fastest during escalations",
    },
    "abu_ali_express_en": {
        "name": "Abu Ali Express (English)",
        "lang": "en", "type": "news",
    },
    "Daniel_Amram": {
        "name": "דניאל עמרם ללא צנזורה — Daniel Amram",
        "lang": "he", "type": "news",
        "followers": "603K+",
        "description": "Israel's #1 Telegram channel. Uncensored security & war reports",
    },
    "amitsegal": {
        "name": "עמית סגל — Amit Segal",
        "lang": "he", "type": "news",
        "followers": "350K+",
        "description": "Channel 12 political correspondent. Only mainstream journalist in top 10",
    },
    "HaTzelChannel": {
        "name": "הצל — HaTzel (The Shadow)",
        "lang": "he", "type": "news",
        "followers": "300K+",
        "description": "Major independent security news channel, one of top 7 in Israel",
    },
    "sdarotali": {
        "name": "חדשות ללא צנזורה — News Without Censorship",
        "lang": "he", "type": "news",
        "followers": "250K+",
        "description": "Uncensored reports from the field. Raw security and military updates",
    },
    "news_kodkodgroup": {
        "name": "קודקוד חדשות — Kodkod News",
        "lang": "he", "type": "news",
        "followers": "250K+",
        "description": "Fast and focused reporting on major events",
    },
    "firstreportsnews": {
        "name": "חדשות ישראל בטלגרם — Israel News on Telegram",
        "lang": "he", "type": "news",
        "followers": "120K+",
        "description": "Breaking news and live war reports. Interception footage and field docs",
    },
    "israel_news_telegram": {
        "name": "ללא צנזורה חדשות ישראל — Uncensored Israel News",
        "lang": "he", "type": "news",
        "description": "Direct uncensored updates from the field, security events in real time",
    },
    "tzenzora": {
        "name": "ללא צנזורה הערוץ הרשמי — Official No Censorship",
        "lang": "he", "type": "news",
        "followers": "173K+",
        "description": "Independent uncensored channel — raw field footage, security events, no filters",
    },
    "hadshotrealtime8": {
        "name": "ערוץ הפרסומים של ישראל — Israel Publications Channel",
        "lang": "he", "type": "news",
        "description": "Real-time news, exclusive reports, leaks and hot topics",
    },

    # ── Unofficial — Breaking news aggregators ──

    "aaborkim": {
        "name": "עכשיו בורקים — Breaking Now",
        "lang": "he", "type": "news",
        "description": "Hebrew breaking news aggregator — very fast",
    },
    "yaborkim": {
        "name": "יש בורקים — Yesh Breaking",
        "lang": "he", "type": "news",
    },
    "newsaborim": {
        "name": "חדשות עוברים — News Passing",
        "lang": "he", "type": "news",
    },

    # ── Unofficial — Arab affairs / Middle East desks ──

    "AbuSalahDesk": {
        "name": "אבו צאלח הדסק הערבי — Abu Salah Arab Desk",
        "lang": "he", "type": "news",
        "description": "Arab world reports and analysis from a Hebrew perspective",
    },
    "MivzakimMehaMizrah": {
        "name": "מבזקים מהמזרח — Breaking from the East",
        "lang": "he", "type": "news",
        "description": "Middle East security flashes — fast, focused, regional updates",
    },

    # ── Unofficial — Security / Borders / Military ──

    "HaCabinetHaBitchoni": {
        "name": "הקבינט הביטחוני — The Security Cabinet",
        "lang": "he", "type": "news",
        "description": "First-hand Arab source reports, border events, Gaza and Lebanon real-time",
    },
    "HAFKAK_ARTZI": {
        "name": "חפ\"ק מרחב ארצי — National Command Post",
        "lang": "he", "type": "news",
        "description": "24/7 security events, terror attacks, sirens, road incidents",
    },

    # ── Official / Government ──

    "idfofficial": {
        "name": "Israel Defense Forces (IDF)",
        "lang": "en", "type": "official",
        "description": "Official IDF channel — security updates and announcements",
    },
    "tzaborkim": {
        "name": "צבא ובטחון — Army & Security Reports",
        "lang": "he", "type": "official",
    },

    # ── Mainstream media on Telegram ──

    "N12News": {
        "name": "חדשות 12 — Channel 12 News",
        "lang": "he", "type": "news",
        "description": "Israel's biggest TV news channel",
    },
    "kann_news": {
        "name": "כאן חדשות — Kan News",
        "lang": "he", "type": "news",
        "description": "Israel's public broadcaster",
    },
    "aaborkim7": {
        "name": "ערוץ 7 — Arutz Sheva / Israel National News",
        "lang": "he", "type": "news",
        "description": "Right-leaning Israeli news outlet, fast on security events",
    },
    "YnetNews": {
        "name": "Ynet — ידיעות אחרונות",
        "lang": "he", "type": "news",
        "description": "Israel's most-read news website",
    },
    "israelhaYomHeb": {
        "name": "ישראל היום — Israel Hayom",
        "lang": "he", "type": "news",
        "description": "Israel's largest circulation newspaper",
    },

    # ══════════════════════════════════════════
    #  TIER 3 — SECONDARY
    #  (Only during active window)
    # ══════════════════════════════════════════

    # ── Military / OSINT / Analysis ──

    "intikitnews": {
        "name": "אינטיקיט חדשות — Intikit News",
        "lang": "he", "type": "analysis",
        "description": "Israeli military/intelligence analysis and news",
    },
    "OpIsrael": {
        "name": "Op Israel (OSINT)",
        "lang": "en", "type": "analysis",
    },

    # ── English Israeli / Jewish News ──

    "JewishBreakingNewsTelegram": {
        "name": "Jewish Breaking News",
        "lang": "en", "type": "news",
        "description": "Real-time Israel war updates in English",
    },
    "IsraelRadar": {
        "name": "Israel Radar",
        "lang": "en", "type": "news",
    },
    "ILtoday": {
        "name": "Israel Today",
        "lang": "en", "type": "news",
        "description": "Israel from the inside — biblical, Zionistic journalism from Jerusalem",
    },

    # ── Regional / Middle East ──

    "Middle_East_Spectator": {
        "name": "Middle East Spectator",
        "lang": "en", "type": "regional",
        "description": "Middle East breaking news — Iran/Hezbollah/Hamas",
    },
    "ramreports": {
        "name": "מבזקי רעם — Ram Reports",
        "lang": "he", "type": "regional",
        "description": "Security/alerts/Arab reports/analysis — with field footage",
    },
}
