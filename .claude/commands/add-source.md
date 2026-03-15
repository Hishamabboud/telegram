Add a new alert data source to the missile alert bot.

The source should be named: $ARGUMENTS

Follow this pattern exactly:
1. Create a new file in `sources/` with an async monitor class
2. The class must accept a callback function in __init__
3. Implement `async run()` as a polling loop with `self._running` flag
4. Implement `async stop()` to set `self._running = False` and close any sessions
5. Use `aiohttp` for HTTP requests with proper timeouts and error handling
6. Add deduplication logic using a hash set
7. Add a corresponding formatter function in `utils/formatter.py`
8. Register the new monitor in `main.py` inside `MissileAlertBot.start()` as a new `asyncio.create_task()`
9. Add any configuration constants to `config/settings.py`
10. Verify the code parses correctly with `python -c "import ast; ast.parse(open('sources/new_file.py').read())"`

Follow the existing code style in `sources/pikud_haoref.py` as the reference implementation.
