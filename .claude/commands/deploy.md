Help deploy the missile alert bot. The user wants to deploy to: $ARGUMENTS

Support these deployment targets:

**Docker (local or VPS):**
1. Build: `docker build -t missile-alert-bot .`
2. Run: `docker run -d --name missile-alerts --restart unless-stopped -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" -e TELEGRAM_CHANNEL_ID="$TELEGRAM_CHANNEL_ID" missile-alert-bot`
3. Check logs: `docker logs -f missile-alerts`

**Systemd (Linux VPS):**
1. Create a systemd service file at `/etc/systemd/system/missile-alert-bot.service`
2. Set WorkingDirectory, ExecStart, environment variables, Restart=always
3. `systemctl enable --now missile-alert-bot`

**Screen/tmux (quick):**
1. `screen -S missile-bot` or `tmux new -s missile-bot`
2. `cd /path/to/missile-alert-bot && python main.py`
3. Detach with Ctrl+A+D (screen) or Ctrl+B+D (tmux)

If the user doesn't specify a target, ask which method they prefer. Always verify environment variables are set before deploying. Suggest a VPS provider (Hetzner, DigitalOcean) if they don't have a server yet.
