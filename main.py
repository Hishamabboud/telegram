"""
🚀 Israeli Missile Alert Telegram Bot — Main Entry Point

Monitors Israeli alert sources and media for missile/rocket activity
and posts real-time updates to a Telegram channel.

Sources:
  1. Pikud HaOref (Home Front Command) — real-time siren alerts
  2. Israeli news RSS feeds — impact reports, interceptions, damage

Usage:
  export TELEGRAM_BOT_TOKEN="your-bot-token"
  export TELEGRAM_CHANNEL_ID="@your_channel"
  python main.py
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone, timedelta

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    LOG_LEVEL,
    LOG_FILE,
    ALERT_BATCH_WINDOW_SECONDS,
)
from sources.pikud_haoref import PikudHaorefMonitor
from sources.news_monitor import IsraeliNewsMonitor
from sources.telegram_channels import TelegramChannelMonitor
from utils.telegram_sender import TelegramSender
from utils.formatter import (
    format_siren_alert,
    format_batched_alert_summary,
    format_news_update,
    format_daily_summary,
    format_status_message,
    format_telegram_channel_update,
)
from utils.stats import AlertStats

# ─── Logging Setup ───
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("missile-alert-bot")


class MissileAlertBot:
    """
    Main bot orchestrator.
    Coordinates all alert sources and sends updates to Telegram.
    """

    def __init__(self):
        self.telegram = TelegramSender()
        self.stats = AlertStats()
        self.pikud_monitor = PikudHaorefMonitor(on_alert_callback=self.on_siren_alert)
        self.news_monitor = IsraeliNewsMonitor(on_news_callback=self.on_news_update)
        self.channel_monitor = TelegramChannelMonitor(on_message_callback=self.on_channel_message)
        self._running = False
        self._daily_summary_task = None

        # ─── Alert Batching ───
        self._alert_batch: list = []          # Buffered alerts
        self._batch_timer_task = None         # The 30s countdown task
        self._batch_lock = asyncio.Lock()

    # ─── Alert Callbacks ───

    async def on_siren_alert(self, alerts):
        """Called when new siren alerts are detected from Pikud HaOref.
        Buffers alerts for 30 seconds, then sends a combined summary."""
        logger.info(f"🚨 New siren alert! {len(alerts)} alert(s) detected")

        # Track stats
        self.stats.record_siren_alerts(alerts)

        # ─── TRIGGER: Activate Telegram channel monitoring ───
        all_areas = []
        for a in alerts:
            all_areas.extend(a.areas_hebrew)
        total_areas = len(all_areas)

        reason = "barrage" if total_areas > 10 else "siren"
        await self.channel_monitor.activate(
            trigger_areas=all_areas[:10],
            reason=reason,
        )

        # ─── Batch alerts ───
        async with self._batch_lock:
            self._alert_batch.extend(alerts)
            logger.info(f"📦 Buffered {len(alerts)} alert(s) — total in batch: {len(self._alert_batch)}")

            # Start the 30s timer if not already running
            if self._batch_timer_task is None or self._batch_timer_task.done():
                self._batch_timer_task = asyncio.create_task(self._flush_alert_batch())

    async def _flush_alert_batch(self):
        """Wait 30 seconds then send a combined summary of all batched alerts."""
        await asyncio.sleep(ALERT_BATCH_WINDOW_SECONDS)

        async with self._batch_lock:
            if not self._alert_batch:
                return

            batch = list(self._alert_batch)
            self._alert_batch.clear()

        logger.info(f"📤 Flushing alert batch: {len(batch)} alert(s)")

        # Send the batched summary (Arabic + English)
        message = format_batched_alert_summary(batch)
        if message:
            success = await self.telegram.send_alert(message)
            if success:
                total = sum(len(a.areas_hebrew) for a in batch)
                logger.info(f"✅ Batched alert summary posted: {total} areas from {len(batch)} alert(s)")
            else:
                logger.error("❌ Failed to post batched alert summary")

    async def on_news_update(self, news_items):
        """Called when new missile-related news articles are found."""
        logger.info(f"📰 New missile-related news: {len(news_items)} article(s)")

        # Track stats
        self.stats.record_news_items(len(news_items))

        # Format and send (silently — news updates don't trigger notifications)
        message = format_news_update(news_items)
        if message:
            success = await self.telegram.send_update(message)
            if success:
                logger.info(f"✅ News update posted: {len(news_items)} articles")
            else:
                logger.error("❌ Failed to post news update")

    async def on_channel_message(self, messages):
        """Called when relevant messages are detected in monitored Telegram channels."""
        logger.info(f"📡 Telegram channel message(s): {len(messages)}")

        # Track stats
        self.stats.record_news_items(len(messages))

        # Format and send
        message = format_telegram_channel_update(messages)
        if message:
            success = await self.telegram.send_alert(message)
            if success:
                logger.info(f"✅ Channel update posted: {len(messages)} messages")
            else:
                logger.error("❌ Failed to post channel update")

    # ─── Daily Summary ───

    async def daily_summary_loop(self):
        """Post a daily summary at midnight Israel time (21:00 UTC / 22:00 UTC)."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                # Calculate next midnight Israel time (~21:00 UTC in winter, 22:00 in summer)
                israel_offset = timedelta(hours=3)  # IDT approximate
                israel_now = now + israel_offset
                tomorrow = israel_now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                next_midnight_utc = tomorrow - israel_offset
                wait_seconds = (next_midnight_utc - now).total_seconds()

                if wait_seconds > 0:
                    logger.info(f"Next daily summary in {wait_seconds/3600:.1f} hours")
                    await asyncio.sleep(min(wait_seconds, 3600))  # Check every hour

                    # Check if it's actually time
                    if (next_midnight_utc - datetime.now(timezone.utc)).total_seconds() > 60:
                        continue

                # Generate and send summary
                data = self.stats.get_summary_data()
                if data["total_alerts"] > 0:
                    message = format_daily_summary(
                        total_alerts=data["total_alerts"],
                        total_areas=data["total_areas"],
                        top_areas=data["top_areas"],
                        news_count=data["news_count"],
                    )
                    await self.telegram.send_update(message)
                    logger.info("📊 Daily summary posted")

                # Reset stats for new day
                self.stats.reset()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily summary loop: {e}")
                await asyncio.sleep(60)

    async def _safe_channel_monitor(self) -> None:
        """Run the Telegram channel monitor, logging errors instead of crashing."""
        try:
            await self.channel_monitor.run()
        except ConnectionError as e:
            logger.warning(f"Telegram channel monitor unavailable: {e}")
            logger.warning("Bot continues without Telegram channel monitoring")
        except Exception as e:
            logger.error(f"Telegram channel monitor failed: {e}")
            logger.warning("Bot continues without Telegram channel monitoring")

    # ─── Main Lifecycle ───

    async def start(self):
        """Start the bot and all monitors."""
        logger.info("=" * 60)
        logger.info("🚀 Missile Alert Bot starting up...")
        logger.info("=" * 60)

        # Validate configuration
        if not TELEGRAM_BOT_TOKEN:
            logger.critical("TELEGRAM_BOT_TOKEN is not set! Exiting.")
            sys.exit(1)
        if not TELEGRAM_CHANNEL_ID:
            logger.critical("TELEGRAM_CHANNEL_ID is not set! Exiting.")
            sys.exit(1)

        # Test Telegram connection
        logger.info("Testing Telegram connection...")
        connected = await self.telegram.test_connection()
        if not connected:
            logger.critical("Failed to connect to Telegram! Check your bot token and channel ID.")
            sys.exit(1)

        logger.info("✅ Telegram connection verified")

        # Start all monitors
        self._running = True

        tasks = [
            asyncio.create_task(self.pikud_monitor.run(), name="pikud-haoref"),
            asyncio.create_task(self.news_monitor.run(), name="news-monitor"),
            asyncio.create_task(self._safe_channel_monitor(), name="telegram-channels"),
            asyncio.create_task(self.daily_summary_loop(), name="daily-summary"),
        ]

        # Send startup message
        await self.telegram.send_update(
            format_status_message(
                "🟢 <b>Bot started successfully</b>\n\n"
                "Monitoring:\n"
                "• Pikud HaOref (real-time alerts) — every 3s\n"
                "• Israeli news feeds — every 60s\n"
                "• Israeli Telegram channels — real-time\n\n"
                "Alerts will be posted automatically."
            )
        )

        logger.info("✅ All monitors running. Waiting for alerts...")

        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Bot tasks cancelled")

    async def shutdown(self):
        """Gracefully shut down the bot."""
        logger.info("🔴 Shutting down...")
        self._running = False

        # Send shutdown message
        try:
            await self.telegram.send_update(
                format_status_message("🔴 <b>Bot shutting down</b>")
            )
        except Exception:
            pass

        # Stop monitors
        await self.pikud_monitor.stop()
        await self.news_monitor.stop()
        await self.channel_monitor.stop()
        await self.telegram.close()

        logger.info("Bot shut down complete.")


# ─── Entry Point ───

def main():
    bot = MissileAlertBot()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        loop.create_task(bot.shutdown())
        loop.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        loop.run_until_complete(bot.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
