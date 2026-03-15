# Israeli Missile Alert Telegram Bot

## About This Project
Async Python bot that monitors Israeli alert systems and media for missile/rocket activity and posts real-time formatted updates to a Telegram channel. Two data sources run as concurrent async tasks.

## Architecture
- **main.py** — Orchestrator: ties monitors together, manages lifecycle, handles daily summaries
- **sources/pikud_haoref.py** — Polls Pikud HaOref (Home Front Command) API every 3s for real-time siren alerts
- **sources/news_monitor.py** — Polls Israeli news RSS feeds (Ynet, ToI, JPost, i24, Kan) every 60s for impact reports
- **sources/telegram_channels.py** — TRIGGER-BASED monitor for 18+ Israeli Telegram channels via Telethon. IDLE by default; activated by Pikud HaOref siren for 10-min window. 3 tiers: Tier 1 (Tzofar/Cumta) always-on, Tier 2 (Abu Ali/IDF/Ch12) scraped on activation, Tier 3 (secondary) only during active window.
- **utils/telegram_sender.py** — Telegram Bot API client with rate limiting, retries, message splitting
- **utils/formatter.py** — Rich HTML message formatting for Telegram (siren alerts, news, channel messages, impact reports, daily summaries)
- **utils/stats.py** — Daily statistics tracker (alert counts, top targeted areas)
- **config/settings.py** — All configuration constants, API URLs, keywords, area translations

## Key Directories
- `config/` — Configuration and constants
- `sources/` — Alert data source monitors (each has `run()` and `stop()` async methods)
- `utils/` — Shared utilities (Telegram sender, formatter, stats)

## Tech Stack
- Python 3.12+
- `aiohttp` for async HTTP (Pikud HaOref API + Telegram Bot API)
- `telethon` for monitoring Telegram channels (user API / MTProto)
- `feedparser` for RSS parsing
- `asyncio` for concurrent task management
- No database — all state is in-memory with deduplication sets

## Commands
- **Run:** `python main.py`
- **Install deps:** `pip install -r requirements.txt`
- **Docker build:** `docker build -t missile-alert-bot .`
- **Docker run:** `docker run -d --restart unless-stopped -e TELEGRAM_BOT_TOKEN="..." -e TELEGRAM_CHANNEL_ID="..." -e TELEGRAM_API_ID="..." -e TELEGRAM_API_HASH="..." -e TELEGRAM_PHONE="..." missile-alert-bot`
- **Syntax check:** `python -c "import ast,os; [ast.parse(open(os.path.join(r,f)).read()) for r,_,fs in os.walk('.') for f in fs if f.endswith('.py')]"`

## Environment Variables (Required)
- `TELEGRAM_BOT_TOKEN` — Bot token from @BotFather (for posting TO your channel)
- `TELEGRAM_CHANNEL_ID` — Channel ID (`@channel_name` or `-100xxxxxxxxxx`)
- `TELEGRAM_API_ID` — From https://my.telegram.org (for reading FROM Israeli channels)
- `TELEGRAM_API_HASH` — From https://my.telegram.org
- `TELEGRAM_PHONE` — Your phone number for Telethon auth (e.g. `+31612345678`)
- `LOG_LEVEL` — Optional, defaults to `INFO`

## Standards
- All source monitors must implement `async run()` and `async stop()` methods
- All source monitors accept an `on_alert_callback` or `on_news_callback` in their constructor
- Use `aiohttp` for all HTTP requests (not `requests`) — the entire bot is async
- Messages use Telegram HTML parse mode, escape with `_escape_html()` from formatter
- Deduplication is mandatory for all sources — use hash sets with periodic trimming
- All network calls must have timeouts and try/except error handling
- Hebrew text must be preserved alongside English translations
- Type hints on all function signatures

## Alert Source Pattern
When adding a new alert source:
1. Create `sources/new_source.py` with a class that takes a callback
2. Implement `async run()` (polling loop) and `async stop()`
3. Add a formatter function in `utils/formatter.py`
4. Register in `main.py` → `MissileAlertBot.start()` as a new `asyncio.create_task()`

## Important Notes
- Pikud HaOref API requires specific headers (Referer + X-Requested-With) — see `config/settings.py`
- The API returns empty string or "null" when no active alerts — this is normal, not an error
- Hebrew BOM character (`\ufeff`) must be stripped from API responses
- Telegram messages have a 4096-char limit — `telegram_sender.py` handles splitting automatically
- Israel timezone handling is simplified (IDT/IST) — for production consider `zoneinfo`
- RSS feeds are filtered by 40+ keywords in English and Hebrew — see `ALERT_KEYWORDS_EN/HE`
- City names from Pikud HaOref are in Hebrew — `AREA_TRANSLATIONS` maps common ones to English

## Known Limitations
- No persistent storage — restarting loses dedup history (alerts may re-post briefly)
- Timezone handling is approximate (no DST transition logic)
- RSS feeds depend on source availability — some may change URLs
- Pikud HaOref API format is undocumented and may change without notice
