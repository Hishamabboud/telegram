Add new city/area translations to the AREA_TRANSLATIONS dictionary in `config/settings.py`.

Cities to add: $ARGUMENTS

For each city:
1. Add the Hebrew name as the key and English name as the value to `AREA_TRANSLATIONS` in `config/settings.py`
2. Also add the city name (English) to the `known_cities` list in `sources/news_monitor.py` → `IsraeliNewsMonitor._extract_locations()`
3. Keep both lists alphabetically sorted
4. Verify the Hebrew text is correct and commonly used in Pikud HaOref alerts
