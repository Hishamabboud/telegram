"""
📊 World Economic Monitor Bot — Main Entry Point

Posts daily economic reports to a Telegram channel:
oil prices, gold, stock indices, currencies, and reserve levels.

Usage:
  python main.py
"""
import asyncio
import logging
import signal
import sys

from dotenv import load_dotenv
load_dotenv()

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    LOG_LEVEL,
    LOG_FILE,
)
from sources.economic_monitor import WorldEconomicMonitor
from utils.telegram_sender import TelegramSender

# ─── Logging Setup ───
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("economic-bot")


class EconomicBot:
    """Posts daily world economic reports to Telegram."""

    def __init__(self):
        self.telegram = TelegramSender()
        self.monitor = WorldEconomicMonitor(on_report_callback=self.on_report)
        self._running = False

    async def on_report(self, report_html: str):
        """Called when a new daily report is ready."""
        success = await self.telegram.send_message(report_html, disable_notification=True)
        if success:
            logger.info("✅ Daily economic report posted")
        else:
            logger.error("❌ Failed to post economic report")

    async def start(self):
        logger.info("=" * 60)
        logger.info("📊 World Economic Monitor starting up...")
        logger.info("=" * 60)

        if not TELEGRAM_BOT_TOKEN:
            logger.critical("TELEGRAM_BOT_TOKEN is not set! Exiting.")
            sys.exit(1)
        if not TELEGRAM_CHANNEL_ID:
            logger.critical("TELEGRAM_CHANNEL_ID is not set! Exiting.")
            sys.exit(1)

        # Test connection
        connected = await self.telegram.test_connection()
        if not connected:
            logger.critical("Failed to connect to Telegram!")
            sys.exit(1)

        logger.info("✅ Telegram connection verified")
        self._running = True

        tasks = [
            asyncio.create_task(self.monitor.run(), name="economic-monitor"),
        ]

        logger.info("✅ Economic monitor running. First report posting now...")

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")

    async def shutdown(self):
        logger.info("🔴 Shutting down...")
        self._running = False
        await self.monitor.stop()
        await self.telegram.close()
        logger.info("Shutdown complete.")


def main():
    bot = EconomicBot()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        loop.create_task(bot.shutdown())
        loop.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
        loop.run_until_complete(bot.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
