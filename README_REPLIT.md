# Replit Upload Guide

## Files to upload
- bot.py
- run_bot.py
- requirements.txt
- .replit
- .env.example
- content_store.json (optional: upload it only if you want to keep the current structure)
- files/ (optional: upload it only if you still use local PDF files)

## Files/folders you should NOT upload
- .env
- .venv/
- .venv-1/
- __pycache__/
- bot.log
- .vscode/

## Replit Secrets
Add these values in Secrets:
- BOT_TOKEN
- ADMIN_ID
- ADMIN_IDS
- REQUIRED_CHANNELS
- CHANNEL_ID

Example:
```env
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
ADMIN_ID=123456789
ADMIN_IDS=123456789,2078667491
REQUIRED_CHANNELS=@your_channel_username
CHANNEL_ID=-1001234567890
```

## Start
Press Run.
The bot will start from run_bot.py.

## UptimeRobot
Use the public Replit URL with:
- /
- /health

Example:
- https://your-repl-name.your-user.repl.co/health

## Notes
- The bot now starts a small HTTP server for keep-alive checks.
- If polling crashes, it retries automatically after 5 seconds.
- For better clarity, use @channel_username in REQUIRED_CHANNELS.
