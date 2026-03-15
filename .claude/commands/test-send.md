Send a test message to the configured Telegram channel to verify the bot connection works.

Steps:
1. Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID` environment variables are set
2. If not set, prompt the user to set them with `export TELEGRAM_BOT_TOKEN="..." && export TELEGRAM_CHANNEL_ID="..."`
3. Run a quick Python script that:
   - Imports TelegramSender from utils.telegram_sender
   - Calls `test_connection()` to verify the bot can reach the channel
   - Reports success or failure with the specific error

Use this test script:
```python
import asyncio
from utils.telegram_sender import TelegramSender

async def test():
    sender = TelegramSender()
    ok = await sender.test_connection()
    print("✅ Connection successful!" if ok else "❌ Connection failed!")
    await sender.close()

asyncio.run(test())
```

Run it from the project root directory.
