# 🚀 Israeli Missile Alert Telegram Bot

A real-time Telegram channel bot that monitors Israeli alert systems and media for missile/rocket activity and posts formatted updates automatically.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Missile Alert Bot                   │
│                                                  │
│  ┌──────────────────┐  ┌─────────────────────┐  │
│  │  Pikud HaOref    │  │  Israeli News RSS   │  │
│  │  Monitor (3s)    │  │  Monitor (60s)      │  │
│  │                  │  │                     │  │
│  │  Real-time siren │  │  • Ynet             │  │
│  │  alerts from     │  │  • Times of Israel  │  │
│  │  Home Front Cmd  │  │  • Jerusalem Post   │  │
│  └────────┬─────────┘  │  • i24 News         │  │
│           │            │  • Kan News          │  │
│           │            └──────────┬──────────┘  │
│           │                       │              │
│           ▼                       ▼              │
│  ┌─────────────────────────────────────────┐    │
│  │         Message Formatter               │    │
│  │  • Siren alerts (with areas/cities)     │    │
│  │  • News updates (with sources/links)    │    │
│  │  • Impact reports                       │    │
│  │  • Daily summaries                      │    │
│  └────────────────────┬────────────────────┘    │
│                       │                          │
│                       ▼                          │
│  ┌─────────────────────────────────────────┐    │
│  │        Telegram Sender                  │    │
│  │  • Rate limiting & retries              │    │
│  │  • Message splitting (>4096 chars)      │    │
│  │  • HTML formatting                      │    │
│  └─────────────────────────────────────────┘    │
│                       │                          │
└───────────────────────┼──────────────────────────┘
                        ▼
              📢 Telegram Channel
```

## Features

- **Real-time siren alerts** — Polls Pikud HaOref every 3 seconds for incoming rocket/missile alerts
- **City & area identification** — Shows which cities/areas are under alert with Hebrew + English names
- **Explosion map (Tzofar-style)** — Monitors the @SabrenNewss channel for explosion/strike reports across the Middle East, then posts a zoomed-in map (affected country filled red + point marker) with a bilingual English+Arabic caption noting the attack type and whether it's confirmed or unconfirmed
- **Israeli media monitoring** — Scans RSS feeds from major Israeli news outlets for impact reports
- **Keyword filtering** — Filters news by 40+ Hebrew and English missile/rocket keywords
- **Smart deduplication** — Avoids duplicate posts for the same alert event
- **Large barrage detection** — Special formatting when many areas are targeted simultaneously
- **Daily summaries** — Posts daily stats at midnight (Israel time) with top targeted areas
- **Graceful error handling** — Retries, rate limiting, exponential backoff
- **Docker ready** — Deploy anywhere with a single container

## Quick Start

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** you receive

### 2. Create a Telegram Channel

1. Create a new Telegram channel (public or private)
2. Add your bot as an **administrator** with permission to post messages
3. Get the channel ID:
   - **Public channel:** Use `@your_channel_name`
   - **Private channel:** Forward a message from the channel to `@userinfobot` to get the numeric ID

### 3. Configure & Run

```bash
# Clone / copy the project
cd missile-alert-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TELEGRAM_CHANNEL_ID="@your_channel_name"

# Run
python main.py
```

### 4. Docker Deployment (Recommended)

```bash
# Build
docker build -t missile-alert-bot .

# Run
docker run -d \
  --name missile-alerts \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="your-token" \
  -e TELEGRAM_CHANNEL_ID="@your_channel" \
  missile-alert-bot
```

`--restart unless-stopped` keeps the bot alive across crashes and reboots. Check
it with `docker logs -f missile-alerts` and update with
`git pull && docker build -t missile-alert-bot . && docker restart missile-alerts`.

## Running 24/7 (PC or Raspberry Pi)

The bot is a long-running process — start it once on an always-on machine and it
polls and posts on its own. Only `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID`
are required (the Telethon Israeli-channel monitor is optional and fails
gracefully if `TELEGRAM_API_ID/HASH/PHONE` are unset).

**Docker (recommended)** — use the commands above with `--restart unless-stopped`.

**Native + systemd (lighter on a Raspberry Pi):**

```bash
cd telegram
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `/etc/systemd/system/missile-bot.service`:

```ini
[Unit]
Description=Missile Alert Bot
After=network-online.target

[Service]
WorkingDirectory=/home/pi/telegram
Environment=TELEGRAM_BOT_TOKEN=your-token
Environment=TELEGRAM_CHANNEL_ID=@your_channel
ExecStart=/home/pi/telegram/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now missile-bot
journalctl -u missile-bot -f      # watch logs
```

**Raspberry Pi notes:**
- Use **64-bit** Raspberry Pi OS — the 32-bit build lacks some `matplotlib`/`pillow` wheels.
- The first `docker build` / `pip install` takes a few minutes (matplotlib, pillow).
- On restart the explosion monitor re-primes its dedup, so it never replays the backlog — only new reports are posted.
- Rendered maps are written to `/tmp` and deleted after sending, so there's no disk buildup.

## Message Examples

### 🔴 Siren Alert
```
🔴🔴🔴 RED ALERT — INCOMING THREAT 🔴🔴🔴

🕐 14:32:15 IDT  •  15 Mar 2026

🚀 Rocket / Missile Alert
צבע אדום: ירי רקטות וטילים

  🚀 Ashkelon (אשקלון)
  🚀 Sderot (שדרות)
  🚀 Netivot (נתיבות)
  🚀 Be'er Sheva (באר שבע)

🛡️ Seek shelter immediately. Stay in protected space for 10 minutes.
──────────────────────────────────
Source: Pikud HaOref (Home Front Command)
```

### 📰 News Update
```
📰 MISSILE NEWS UPDATE
🕐 14:45:00 IDT  •  15 Mar 2026

1. Iron Dome intercepts multiple rockets over southern Israel
   Several rockets were fired toward...
   📎 Read more (Times of Israel)
──────────────────────────────────
```

## Project Structure

```
missile-alert-bot/
├── main.py                    # Entry point & orchestrator
├── config/
│   ├── settings.py            # All configuration & constants
├── sources/
│   ├── pikud_haoref.py        # Home Front Command alert monitor
│   ├── news_monitor.py        # Israeli news RSS feed monitor
│   ├── telegram_channels.py   # Israeli Telegram channel monitor (Telethon)
│   ├── sabren_news.py         # Sabereen News explosion-map monitor
├── utils/
│   ├── formatter.py           # Telegram message formatting
│   ├── telegram_sender.py     # Telegram Bot API client (send_message/send_photo)
│   ├── me_geocoder.py         # Middle East location → coordinates gazetteer
│   ├── attack_formatter.py    # Attack-type/confirmation classifier + caption
│   ├── map_renderer.py        # Tzofar-style explosion map (matplotlib)
│   ├── stats.py               # Daily statistics tracker
├── assets/
│   ├── countries.geo.json     # Bundled country borders (offline map)
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## Configuration

All settings are in `config/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `PIKUD_HAOREF_POLL_INTERVAL` | 3s | How often to check for siren alerts |
| `NEWS_RSS_POLL_INTERVAL` | 60s | How often to check news feeds |
| `SABREN_POLL_INTERVAL` | 90s | How often to check @SabrenNewss for explosion reports |
| `DEDUP_WINDOW_SECONDS` | 300s | Deduplication window for alerts |

## Adding More Sources

To add a new alert source:

1. Create a new file in `sources/`
2. Implement `async run()` and `async stop()` methods
3. Call the callback function with parsed alerts
4. Register it in `main.py`'s `MissileAlertBot.start()`

## Customization

- **Change channel branding:** Edit `@YourChannelName` in `utils/formatter.py`
- **Add/remove RSS feeds:** Edit `NEWS_RSS_FEEDS` in `config/settings.py`
- **Adjust keywords:** Edit `ALERT_KEYWORDS_EN` / `ALERT_KEYWORDS_HE` in settings
- **Add city translations:** Extend `AREA_TRANSLATIONS` in settings

## Notes

- The Pikud HaOref API is a **public** Israeli government resource
- Bot requires stable internet connection — recommended to run on a VPS or cloud instance
- For production, consider adding: database persistence, health checks, monitoring, and a process manager like `supervisord`
