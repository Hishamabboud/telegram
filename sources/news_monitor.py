"""
Israeli Media News Monitor
Monitors RSS feeds and news sites for missile/rocket impact reports.
Provides context beyond the raw siren alerts (damage reports, interceptions, etc.)
"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp
import feedparser

from config.settings import (
    NEWS_RSS_FEEDS,
    NEWS_RSS_POLL_INTERVAL,
    ALERT_KEYWORDS_EN,
    ALERT_KEYWORDS_HE,
    STRICT_WAR_KEYWORDS_EN,
    STRICT_WAR_KEYWORDS_HE,
    DEDUP_WINDOW_SECONDS,
)

logger = logging.getLogger(__name__)


class NewsItem:
    """A single news article related to missile activity."""

    def __init__(self, title: str, summary: str, link: str, source: str, published: Optional[datetime] = None):
        self.title = title
        self.summary = summary
        self.link = link
        self.source = source
        self.published = published or datetime.now(timezone.utc)
        self.id = hashlib.md5(f"{title}{link}".encode()).hexdigest()

    @property
    def snippet(self) -> str:
        """Return a short clean text snippet from the summary."""
        clean = re.sub(r'<[^>]+>', '', self.summary)  # Strip HTML tags
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean[:300] + "..." if len(clean) > 300 else clean

    def __eq__(self, other):
        return isinstance(other, NewsItem) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


class IsraeliNewsMonitor:
    """
    Monitors Israeli news RSS feeds for missile/rocket related articles.
    Filters articles by keyword relevance and deduplicates.
    """

    def __init__(self, on_news_callback):
        self.callback = on_news_callback
        self.seen_ids: set[str] = set()
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        # General keywords for initial relevance check
        self.all_keywords = [kw.lower() for kw in ALERT_KEYWORDS_EN + ALERT_KEYWORDS_HE]
        # Strict keywords — article must match at least one to pass
        self.strict_keywords = [kw.lower() for kw in STRICT_WAR_KEYWORDS_EN + STRICT_WAR_KEYWORDS_HE]

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout, trust_env=True)
        return self._session

    def _is_relevant(self, title: str, summary: str) -> bool:
        """Check if an article is relevant to Israel-Iran war activity.
        Uses strict filtering: must match a general keyword AND a strict
        Israel-Iran war keyword to avoid showing unrelated country news."""
        combined = f"{title} {summary}".lower()
        has_general = any(kw in combined for kw in self.all_keywords)
        if not has_general:
            return False
        # Must also match a strict Israel-Iran war keyword
        return any(kw in combined for kw in self.strict_keywords)

    def _extract_locations(self, text: str) -> list[str]:
        """Try to extract Israeli city/location names from text."""
        known_cities = [
            "Tel Aviv", "Haifa", "Jerusalem", "Be'er Sheva", "Beer Sheva",
            "Ashkelon", "Ashdod", "Sderot", "Netivot", "Ofakim",
            "Kiryat Shmona", "Nahariya", "Akko", "Acre", "Karmiel",
            "Safed", "Tiberias", "Afula", "Hadera", "Netanya",
            "Herzliya", "Ra'anana", "Petah Tikva", "Rishon LeZion",
            "Rehovot", "Modi'in", "Eilat", "Dimona",
            "northern Israel", "southern Israel", "central Israel",
            "Gaza envelope", "Gaza border", "Galilee", "Golan",
            "Negev", "Dan region", "Sharon", "Western Galilee",
            "Upper Galilee", "Lower Galilee", "Jezreel Valley",
        ]
        found = []
        text_lower = text.lower()
        for city in known_cities:
            if city.lower() in text_lower:
                found.append(city)
        return found

    async def fetch_feed(self, name: str, url: str) -> list[NewsItem]:
        """Fetch and parse a single RSS feed."""
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"RSS feed {name} returned {response.status}")
                    return []
                text = await response.text()

            feed = feedparser.parse(text)
            items = []

            for entry in feed.entries[:20]:  # Check latest 20 entries
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                published = None

                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                # Only include if relevant to missile/rocket activity
                if self._is_relevant(title, summary):
                    item = NewsItem(
                        title=title,
                        summary=summary,
                        link=link,
                        source=name,
                        published=published,
                    )
                    items.append(item)

            return items

        except Exception as e:
            logger.error(f"Error fetching RSS feed {name}: {e}")
            return []

    async def poll_all_feeds(self) -> list[NewsItem]:
        """Poll all configured RSS feeds concurrently."""
        tasks = [
            self.fetch_feed(name, url)
            for name, url in NEWS_RSS_FEEDS.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Feed error: {result}")

        return all_items

    async def poll_once(self):
        """Single poll — fetch feeds, filter new items, and report."""
        items = await self.poll_all_feeds()
        new_items = []

        for item in items:
            if item.id not in self.seen_ids:
                self.seen_ids.add(item.id)
                new_items.append(item)

        # Trim dedup set
        if len(self.seen_ids) > 2000:
            items_list = list(self.seen_ids)
            self.seen_ids = set(items_list[len(items_list)//2:])

        if new_items:
            # Sort by published date, newest first
            new_items.sort(key=lambda x: x.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            await self.callback(new_items)

    async def run(self):
        """Main polling loop for news feeds."""
        self._running = True
        logger.info("🟢 Israeli News monitor started")

        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error(f"Error in news poll loop: {e}")
            await asyncio.sleep(NEWS_RSS_POLL_INTERVAL)

    async def stop(self):
        """Stop the monitor."""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("🔴 Israeli News monitor stopped")
