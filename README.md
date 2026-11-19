# 🗨 Stranger Chaos Bot

> Connect with strangers and chat privately without revealing your Telegram account.

---

## ✨ Features

| Feature | Free | Premium |
|---|---|---|
| Anonymous stranger search | ✅ | ✅ |
| Text, photo, sticker, voice relay | ✅ | ✅ |
| /link — share your profile | ✅ | ✅ |
| /report — report bad users | ✅ | ✅ |
| Like 👍 / Dislike 👎 rating | ✅ | ✅ |
| /block — block current partner | ❌ | ✅ |
| /del — delete for both sides | ❌ | ✅ |
| Unlimited searches | ❌ | ✅ |

---

## 📂 Project Structure

```
stranger_chaos/
├── bot.py            ← entry point
├── config.py         ← all settings (token, admin IDs, feature flags)
├── database.py       ← JSON-based data layer
├── texts.py          ← all message strings
├── keyboards.py      ← inline & reply keyboards
├── plugins/
│   ├── start.py      ← /start, /help
│   ├── chat.py       ← /search, /next, /stop, message relay, ratings
│   ├── commands.py   ← /link, /block, /blocklist, /unblock, /del, /report
│   └── admin.py      ← /stats, /ban, /unban, /premium, /broadcast, /reports
├── requirements.txt
├── render.yaml       ← Render.com free-tier deploy
└── .env.example
```

---

## 🚀 Setup

### 1. Create a bot
- Open [@BotFather](https://t.me/BotFather)
- `/newbot` → give it a name and username
- Copy the **token**

### 2. Set up commands in BotFather
```
search - Find a stranger
next - Skip to a new partner
stop - End current chat
link - Get your profile link
block - Block current partner (premium)
blocklist - View blocked users
unblock - Unblock a user by ID
del - Delete message for both sides (premium)
report - Report current partner
help - Show help
```

### 3. Configure
Copy `.env.example` → `.env` and fill in:
- `BOT_TOKEN` — from BotFather
- `ADMIN_IDS` — your Telegram numeric ID (get it from @userinfobot)

### 4. Run locally
```bash
pip install -r requirements.txt
python bot.py
```

### 5. Deploy to Render (free)
1. Push this folder to a GitHub repo
2. Go to [render.com](https://render.com) → New → **Background Worker**
3. Connect your repo
4. Set env vars `BOT_TOKEN` and `ADMIN_IDS` in the dashboard
5. Deploy!

---

## 🛡 Admin Commands

| Command | Description |
|---|---|
| `/stats` | Bot statistics |
| `/ban <id> [reason]` | Ban a user |
| `/unban <id>` | Unban a user |
| `/premium <id>` | Grant premium |
| `/unpremium <id>` | Revoke premium |
| `/addcoin <id> <n>` | Add search coins |
| `/broadcast <msg>` | Message all users |
| `/reports` | List open reports |
| `/resolve <n>` | Resolve report |

---

## 🗄 Swapping the Database

`database.py` is the only file that touches storage. Replace it with SQLite, PostgreSQL, or Redis — the rest of the bot doesn't change.

---

## 📋 Block Limit
Users can block up to **30** people (configurable via `MAX_BLOCK_LIST` in `config.py`).

---

Made with ❤️ using [aiogram 3](https://docs.aiogram.dev/)
