# 📋 Setup Guide — Link Your Telegram Channel

This guide walks you through connecting the bot to your Telegram channel in 3 steps.

---

## Step 1: Create Your Telegram Bot (for POSTING alerts)

This bot will post messages to your channel.

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name: e.g. `Israel Missile Alerts`
4. Choose a username: e.g. `il_missile_alerts_bot`
5. **Copy the token** — it looks like: `7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

```bash
export TELEGRAM_BOT_TOKEN="7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

---

## Step 2: Create & Link Your Telegram Channel

### Create the channel:
1. Open Telegram → Hamburger menu (☰) → **New Channel**
2. Name it: e.g. `🚀 Israel Missile Alerts`
3. Choose **Public** and set a username: e.g. `@il_missile_alerts`
4. (Optional) Add a description and photo

### Add the bot as admin:
1. Open your channel → **Channel Info** (tap the name at top)
2. Tap **Administrators** → **Add Administrator**
3. Search for your bot username (e.g. `@il_missile_alerts_bot`)
4. Grant permissions: ✅ Post Messages, ✅ Edit Messages
5. Tap **Save**

### Set the channel ID:

**For public channels:**
```bash
export TELEGRAM_CHANNEL_ID="@il_missile_alerts"
```

**For private channels:**
1. Forward any message from your channel to `@userinfobot` on Telegram
2. It will reply with the numeric channel ID (starts with `-100`)
```bash
export TELEGRAM_CHANNEL_ID="-1001234567890"
```

---

## Step 3: Get Telegram API Credentials (for READING Israeli channels)

This is needed so the bot can monitor other channels (Abu Ali, Tzofar, IDF, etc.)

1. Go to **https://my.telegram.org**
2. Log in with your **phone number**
3. Click **API development tools**
4. Fill in:
   - **App title:** `MissileAlertBot`
   - **Short name:** `missilealert`
   - **Platform:** `Other`
5. Click **Create application**
6. **Copy** the `api_id` and `api_hash`

```bash
export TELEGRAM_API_ID="12345678"
export TELEGRAM_API_HASH="abcdef1234567890abcdef1234567890"
export TELEGRAM_PHONE="+31612345678"  # Your phone number
```

> ⚠️ **First run only:** Telethon will ask you to enter a verification code
> sent to your Telegram app. This happens once — after that, a session file
> is created and you won't need to re-authenticate.

---

## All Environment Variables Together

Copy this block, fill in your values, and paste into your terminal:

```bash
# Bot for posting to YOUR channel
export TELEGRAM_BOT_TOKEN="7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TELEGRAM_CHANNEL_ID="@your_channel_name"

# User API for reading ISRAELI channels
export TELEGRAM_API_ID="12345678"
export TELEGRAM_API_HASH="abcdef1234567890abcdef1234567890"
export TELEGRAM_PHONE="+31612345678"
```

Or create a `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
nano .env  # fill in your values
```

Then load it:
```bash
export $(grep -v '^#' .env | xargs)
```

---

## Run the Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Run (first time will ask for Telegram verification code)
python main.py
```

You should see:
```
🚀 Missile Alert Bot starting up...
✅ Telegram connection verified
✅ Monitoring: Tzofar — Red Alert (English) (tzevaadom_en)
✅ Monitoring: Abu Ali Express (abu_ali_express)
✅ Monitoring: Israel Defense Forces (IDF) (idfofficial)
... (more channels)
🟢 All monitors running. Waiting for alerts...
```

---

## Israeli Channels Being Monitored

The bot comes pre-configured to monitor these channels:

### 🔴 Alert Channels (Real-time sirens)
| Channel | Username | Language |
|---------|----------|----------|
| Tzofar (Red Alert) | `@tzevaadom` | Hebrew |
| Tzofar (English) | `@tzevaadom_en` | English |
| Cumta Alerts | `@CumtaAlertsChannel` | Hebrew |
| Cumta (English) | `@CumtaAlertsEnglishChannel` | English |

### 📰 News Channels
| Channel | Username | Language |
|---------|----------|----------|
| Abu Ali Express | `@abu_ali_express` | Hebrew |
| Abu Ali (English) | `@abu_ali_express_en` | English |
| Channel 12 News | `@N12News` | Hebrew |
| Kan News | `@kann_news` | Hebrew |
| Breaking Now | `@aaborkim` | Hebrew |
| Yesh Breaking | `@yaborkim` | Hebrew |
| News Feed | `@newsaborim` | Hebrew |

### 🎖️ Official / Military
| Channel | Username | Language |
|---------|----------|----------|
| IDF Official | `@idfofficial` | English |
| Army & Security | `@tzaborkim` | Hebrew |
| Intikit News | `@intikitnews` | Hebrew |

### 🌍 Regional
| Channel | Username | Language |
|---------|----------|----------|
| Jewish Breaking News | `@JewishBreakingNewsTelegram` | English |
| Israel Radar | `@IsraelRadar` | English |
| Middle East Spectator | `@Middle_East_Spectator` | English |
| Ram Reports | `@RamAbdallah` | Hebrew |

---

## Add or Remove Channels

Edit `MONITORED_CHANNELS` in `config/settings.py`:

```python
# Add a new channel
"new_channel_username": {
    "name": "Display Name",
    "lang": "he",       # "he" or "en"
    "type": "news",     # "alert", "news", "official", "analysis", "regional"
},
```

Or in Claude Code: `/add-source telegram_channel_name`

---

## Troubleshooting

**"Bot token invalid"**
→ Go back to @BotFather, send `/token` and select your bot to get a fresh token

**"Chat not found" / "Forbidden"**
→ Make sure the bot is added as admin to your channel with posting permissions

**"Could not resolve channel"**
→ The channel username may have changed. Check by opening `t.me/channel_username` in your browser

**"Phone number invalid"**
→ Include country code: `+31612345678` not `0612345678`

**"Session expired"**
→ Delete the `missile_alert_session.session` file and re-run to re-authenticate

**Telegram channel monitor not starting**
→ If `TELEGRAM_API_ID` is empty, the channel monitor is skipped gracefully. The bot still works with Pikud HaOref + RSS feeds.
