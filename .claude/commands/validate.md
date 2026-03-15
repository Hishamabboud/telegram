Run a full validation check on the missile alert bot codebase.

Perform the following checks:
1. **Syntax check** — Parse all .py files with `ast.parse()` to verify no syntax errors
2. **Import check** — Try importing each module: `python -c "from config.settings import *; from sources.pikud_haoref import *; from sources.news_monitor import *; from utils.formatter import *; from utils.telegram_sender import *; from utils.stats import *"`
3. **Dependency check** — Verify all packages in requirements.txt are installed: `pip show aiohttp feedparser beautifulsoup4`
4. **Config validation** — Confirm PIKUD_HAOREF_URL, NEWS_RSS_FEEDS, ALERT_KEYWORDS_EN, and ALERT_KEYWORDS_HE are non-empty
5. **Formatter test** — Call each format function with sample data and verify output is non-empty and valid HTML
6. **Docker build test** — If Docker is available, run `docker build --dry-run .`

Report results as a clear pass/fail checklist.
