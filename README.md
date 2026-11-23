# 🗨️ Stranger Chaos Bot

> Connect with strangers and chat privately without revealing your Telegram account.

Built in **Rust** with [Teloxide](https://teloxide.rs/) and persistent JSON storage.

## Run locally

```bash
cp .env.example .env
# Add BOT_TOKEN and ADMIN_IDS
cargo run --release
```

## Build

```bash
cargo build --release
./target/release/stranger-chaos-bot
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | ❌ | Comma-separated numeric Telegram IDs |
| `DB_PATH` | ❌ | Database file path, default `data/db.json` |

## Commands

- `/start` — register and restart
- `/help` — show commands
- `/search` — find a stranger
- `/stop` — leave the current chat
