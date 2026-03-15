"""
Alert Statistics Tracker
Tracks daily alert counts, affected areas, and generates summaries.
"""
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class AlertStats:
    """Tracks and aggregates alert statistics."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all counters for a new day."""
        self.total_alert_events = 0
        self.total_areas_alerted = 0
        self.area_counter = Counter()
        self.news_article_count = 0
        self.alert_timestamps = []
        self.last_reset = datetime.now(timezone.utc)

    def record_siren_alerts(self, alerts):
        """Record siren alert events."""
        for alert in alerts:
            self.total_alert_events += 1
            for area in alert.areas_hebrew:
                self.area_counter[area] += 1
                self.total_areas_alerted += 1
            self.alert_timestamps.append(datetime.now(timezone.utc))

    def record_news_items(self, count: int):
        """Record the number of news articles found."""
        self.news_article_count += count

    @property
    def top_areas(self) -> list[tuple[str, int]]:
        """Get top targeted areas."""
        return self.area_counter.most_common(15)

    @property
    def unique_areas_count(self) -> int:
        return len(self.area_counter)

    def should_reset(self) -> bool:
        """Check if it's time to reset (new day in Israel time)."""
        now = datetime.now(timezone.utc) + timedelta(hours=3)  # Approx Israel time
        last = self.last_reset + timedelta(hours=3)
        return now.date() > last.date()

    def get_summary_data(self) -> dict:
        """Get summary data for formatting."""
        return {
            "total_alerts": self.total_alert_events,
            "total_areas": self.total_areas_alerted,
            "unique_areas": self.unique_areas_count,
            "top_areas": self.top_areas,
            "news_count": self.news_article_count,
        }
