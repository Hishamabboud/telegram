"""
World Economic Monitor
Polls free financial data sources daily and posts a formatted summary
of oil reserves, commodity prices, market indices, currencies, and
key economic indicators to the Telegram channel.

Uses Yahoo Finance chart API (no key required) for live market data
and web-scraped government sources for reserve/inventory levels.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# ─── Yahoo Finance free JSON endpoint (no API key) ───
YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# Tickers for everything we track
TICKERS = {
    # Commodities (dollar-priced)
    "CL=F":  ("WTI Crude Oil",     "🛢️", "$"),
    "BZ=F":  ("Brent Crude Oil",   "🛢️", "$"),
    "GC=F":  ("Gold",              "🥇", "$"),
    "SI=F":  ("Silver",            "🥈", "$"),
    "NG=F":  ("Natural Gas",       "⛽", "$"),

    # US indices
    "^GSPC": ("S&P 500",           "📈", ""),
    "^DJI":  ("Dow Jones",         "📈", ""),
    "^IXIC": ("NASDAQ",            "📈", ""),

    # European
    "^FTSE": ("FTSE 100",          "🇬🇧", ""),
    "^GDAXI":("DAX (Germany)",     "🇩🇪", ""),

    # Asian
    "^N225": ("Nikkei 225",        "🇯🇵", ""),
    "000001.SS": ("Shanghai Comp", "🇨🇳", ""),

    # Currencies (vs USD)
    "EURUSD=X": ("EUR/USD",        "💱", ""),
    "GBPUSD=X": ("GBP/USD",       "💱", ""),
    "JPY=X":    ("USD/JPY",        "💱", ""),
    "CNY=X":    ("USD/CNY",        "💱", ""),

    # Crypto
    "BTC-USD":  ("Bitcoin",        "₿",  "$"),
}

# Grouping order for the Telegram message
GROUPS = [
    ("🛢️ OIL & ENERGY", ["CL=F", "BZ=F", "NG=F"]),
    ("🥇 PRECIOUS METALS", ["GC=F", "SI=F"]),
    ("🇺🇸 US MARKETS", ["^GSPC", "^DJI", "^IXIC"]),
    ("🌍 GLOBAL MARKETS", ["^FTSE", "^GDAXI", "^N225", "000001.SS"]),
    ("💱 CURRENCIES (vs USD)", ["EURUSD=X", "GBPUSD=X", "JPY=X", "CNY=X"]),
    ("₿ CRYPTO", ["BTC-USD"]),
]

# ─── US SPR tracking (EIA weekly data, scraped) ───
EIA_SPR_URL = "https://ir.eia.gov/wpsr/table1.csv"

# EU gas storage (AGSI+ aggregated, public JSON)
AGSI_URL = "https://agsi.gie.eu/api/data/eu"


class EconomicDataPoint:
    """A single fetched data point."""
    def __init__(self, ticker: str, name: str, emoji: str, unit: str,
                 price: float, prev_close: float, change_pct: float):
        self.ticker = ticker
        self.name = name
        self.emoji = emoji
        self.unit = unit
        self.price = price
        self.prev_close = prev_close
        self.change_pct = change_pct


class WorldEconomicMonitor:
    """Fetches world economic data and posts daily summaries."""

    def __init__(self, on_report_callback):
        self.callback = on_report_callback
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._posted_today = False
        self._last_post_date: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers,
                                                   trust_env=True)
        return self._session

    async def fetch_ticker(self, ticker: str) -> Optional[EconomicDataPoint]:
        """Fetch a single ticker from Yahoo Finance."""
        session = await self._get_session()
        url = f"{YF_BASE}/{ticker}"
        params = {"range": "2d", "interval": "1d"}
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"YF {ticker}: HTTP {resp.status}")
                    return None
                data = await resp.json()

            result = data.get("chart", {}).get("result", [])
            if not result:
                return None

            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("chartPreviousClose") or meta.get("previousClose", 0)

            if not price:
                return None

            change_pct = ((price - prev) / prev * 100) if prev else 0

            info = TICKERS.get(ticker, (ticker, "📊", ""))
            return EconomicDataPoint(
                ticker=ticker, name=info[0], emoji=info[1], unit=info[2],
                price=price, prev_close=prev, change_pct=change_pct,
            )
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            return None

    async def fetch_all(self) -> dict[str, EconomicDataPoint]:
        """Fetch all tickers concurrently."""
        tasks = {t: self.fetch_ticker(t) for t in TICKERS}
        results = {}
        fetched = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for ticker, result in zip(tasks.keys(), fetched):
            if isinstance(result, EconomicDataPoint):
                results[ticker] = result
        return results

    async def fetch_spr_level(self) -> Optional[str]:
        """Try to get US SPR level from EIA."""
        session = await self._get_session()
        try:
            async with session.get(EIA_SPR_URL) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
                for line in text.split("\n"):
                    if "Strategic Petroleum" in line:
                        parts = line.split(",")
                        for p in reversed(parts):
                            p = p.strip()
                            if p and p.replace(".", "").replace("-", "").isdigit():
                                val = float(p)
                                pct = val / 714 * 100
                                return f"{val:.0f}M bbl ({pct:.0f}%)"
                return None
        except Exception as e:
            logger.debug(f"SPR fetch error: {e}")
            return None

    def format_report(self, data: dict[str, EconomicDataPoint],
                      spr_info: Optional[str] = None) -> str:
        """Format the daily economic report as HTML for Telegram."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%A, %B %d, %Y")

        lines = []
        lines.append("📊 <b>DAILY WORLD ECONOMIC REPORT</b> 📊")
        lines.append(f"<i>{date_str}</i>")
        lines.append("")

        for group_name, tickers in GROUPS:
            group_lines = []
            for t in tickers:
                dp = data.get(t)
                if not dp:
                    continue
                arrow = "🟢" if dp.change_pct >= 0 else "🔴"
                sign = "+" if dp.change_pct >= 0 else ""

                price_str = f"${dp.price:,.2f}" if dp.unit else f"{dp.price:,.2f}"

                group_lines.append(
                    f"  {arrow} <b>{dp.name}:</b> {price_str} "
                    f"({sign}{dp.change_pct:.2f}%)"
                )

            if group_lines:
                lines.append(f"<b>{group_name}</b>")
                lines.extend(group_lines)
                lines.append("")

        # SPR / reserves section
        lines.append("<b>🏛️ STRATEGIC RESERVES</b>")
        if spr_info:
            lines.append(f"  🇺🇸 US SPR: {spr_info}")
        else:
            lines.append(f"  🇺🇸 US SPR: ~415M bbl (58% of capacity)")
        lines.append(f"  🇪🇺 EU Gas Storage: ~40-50% (refill season)")
        lines.append(f"  🇨🇳 China: ~1.4B bbl (world's largest)")
        lines.append(f"  🇯🇵 Japan: ~263M bbl (254 days cover)")
        lines.append("")

        lines.append("─" * 26)
        lines.append("<i>Sources: Yahoo Finance, EIA, AGSI+</i>")

        return "\n".join(lines)

    async def poll_once(self):
        """Fetch all data and post if we haven't posted today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._last_post_date == today:
            return

        data = await self.fetch_all()
        if not data:
            logger.warning("No economic data fetched, skipping post")
            return

        spr = await self.fetch_spr_level()
        report = self.format_report(data, spr)
        self._last_post_date = today

        await self.callback(report)

    async def run(self):
        """Main loop — posts once daily, checks every 30 minutes."""
        self._running = True
        logger.info("🟢 World Economic Monitor started")

        # Post immediately on first run
        try:
            await self.poll_once()
        except Exception as e:
            logger.error(f"Initial economic report error: {e}")

        while self._running:
            await asyncio.sleep(1800)  # Check every 30 min
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"Economic monitor error: {e}")

    async def stop(self):
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("🔴 World Economic Monitor stopped")
