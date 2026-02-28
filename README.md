# otp-bot

Minimal local script that polls Gmail via IMAP, extracts 6-digit OTP codes, and forwards them to Telegram.

## Setup
1. Enable IMAP in Gmail settings.
2. Create an app password (Google Account -> Security -> App passwords).
3. Create a Telegram bot via @BotFather and get the bot token.
4. Get your chat IDs (e.g. message your bot, then use any chat-id helper bot).

## Configure
Copy `config.example.env` to `.env` and fill values.

## Run
```bash
uv sync
uv run python otp_forwarder.py
```

## Notes
- By default it searches only `UNSEEN` emails and filters by `BANK_FROM` if set.
- It marks messages as seen only after a valid 6-digit OTP was sent.
