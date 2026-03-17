"""
Telegram Bot Sender
Handles sending formatted messages to the Telegram channel.
Includes rate limiting, retry logic, and message splitting for long messages.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
MAX_MESSAGE_LENGTH = 4096  # Telegram's max message length


class TelegramSender:
    """Sends messages to a Telegram channel via the Bot API."""

    def __init__(self, bot_token: str = None, channel_id: str = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.channel_id = channel_id or TELEGRAM_CHANNEL_ID
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_delay = 0.5  # Min delay between messages (seconds)
        self._last_send_time = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout, trust_env=True)
        return self._session

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
        disable_notification: bool = False,
    ) -> bool:
        """
        Send a message to the configured Telegram channel.
        Automatically splits long messages.
        
        Returns True if successful, False otherwise.
        """
        if not self.bot_token or not self.channel_id:
            logger.error("Telegram bot token or channel ID not configured!")
            return False

        if not text.strip():
            return False

        # Split long messages
        chunks = self._split_message(text)
        success = True

        for chunk in chunks:
            ok = await self._send_single(
                chunk, parse_mode, disable_web_page_preview, disable_notification
            )
            if not ok:
                success = False
            # Rate limiting
            await asyncio.sleep(self._rate_limit_delay)

        return success

    async def _send_single(
        self,
        text: str,
        parse_mode: str,
        disable_web_page_preview: bool,
        disable_notification: bool,
    ) -> bool:
        """Send a single message chunk to Telegram."""
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
            "disable_notification": disable_notification,
        }

        for attempt in range(3):  # 3 retries
            try:
                session = await self._get_session()
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()

                    if data.get("ok"):
                        logger.info(f"Message sent to {self.channel_id}")
                        return True

                    error_code = data.get("error_code", 0)
                    description = data.get("description", "Unknown error")

                    # Handle rate limiting (429)
                    if error_code == 429:
                        retry_after = data.get("parameters", {}).get("retry_after", 5)
                        logger.warning(f"Rate limited. Retrying after {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue

                    # Handle other errors
                    logger.error(f"Telegram API error: {error_code} - {description}")

                    # If it's a formatting error, try sending without parse mode
                    if error_code == 400 and "parse" in description.lower():
                        logger.info("Retrying without HTML parse mode...")
                        payload["parse_mode"] = ""
                        continue

                    return False

            except aiohttp.ClientError as e:
                logger.error(f"Network error sending to Telegram (attempt {attempt+1}): {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                logger.error(f"Unexpected error sending to Telegram: {e}")
                return False

        return False

    async def send_alert(self, text: str) -> bool:
        """Send an urgent alert (with notification sound)."""
        return await self.send_message(text, disable_notification=False)

    async def send_update(self, text: str) -> bool:
        """Send a non-urgent update (silent notification)."""
        return await self.send_message(text, disable_notification=True)

    def _split_message(self, text: str) -> list[str]:
        """Split a message into chunks that fit Telegram's max length."""
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        chunks = []
        lines = text.split("\n")
        current_chunk = ""

        for line in lines:
            if len(current_chunk) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text[:MAX_MESSAGE_LENGTH]]

    async def test_connection(self) -> bool:
        """Test bot connection and channel access."""
        try:
            session = await self._get_session()
            # Test bot token
            async with session.get(f"{self.api_base}/getMe") as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.error("Invalid bot token!")
                    return False
                bot_name = data["result"]["username"]
                logger.info(f"Bot connected: @{bot_name}")

            # Test channel access
            test_result = await self.send_message(
                "🤖 <b>Missile Alert Bot</b> is now online and monitoring.\n\n"
                "Sources:\n"
                "• Pikud HaOref (Home Front Command) — real-time alerts\n"
                "• Israeli media RSS feeds — impact reports & news\n\n"
                "<i>Bot will post alerts automatically.</i>",
                disable_notification=True,
            )
            return test_result

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
