# 🗨 Stranger Chaos Bot

> Connect with strangers and chat privately without revealing your Telegram account.

Built with [aiogram 3](https://docs.aiogram.dev/) · Python 3.10+ · JSON storage (swappable)

---

## ✨ Features

| Feature | Free | Premium |
|---|---|---|
| Anonymous stranger search | ✅ | ✅ |
| Text, photo, sticker, voice, video, document relay | ✅ | ✅ |
| 🎯 Interest-based matching (`/interests`) | ✅ | ✅ |
| 🧊 `/icebreaker` conversation starters | ✅ | ✅ |
| 🎁 `/daily` bonus searches with streak | ✅ | ✅ |
| ↩️ Reply threading across the relay | ✅ | ✅ |
| `/link` — send your profile to your partner | ✅ | ✅ |
| `/report` — report bad users (admins alerted instantly) | ✅ | ✅ |
| Like 👍 / Dislike 👎 rating | ✅ | ✅ |
| 🔎 Find Girl / Find Boy | ❌ | ✅ |
| `/block` — block current partner | ❌ | ✅ |
| `/del` — delete a message for both sides | ❌ | ✅ |
| More daily searches | 100 | 200 |

---

## 📂 Project Structure

```
├── bot.py            ← entry point
├── config.py         ← settings (token, admins, limits, interests, bonus)
├── database.py       ← JSON data layer (cached, atomic writes)
├── matching.py       ← gender filters + interest scoring
├── middlewares.py    ← ban check / user registration
├── utils.py          ← HTML escape, message map, admin alerts
├── texts.py          ← all message strings (+ icebreaker questions)
├── keyboards.py      ← inline & reply keyboards
├── states.py         ← FSM states
├── plugins/
│   ├── start.py      ← /start, /profile, /interests, /daily
│   ├── chat.py       ← search/next/stop, matching, relay, /icebreaker, ratings
│   ├── commands.py   ← /link, /block, /blocklist, /unblock, /del, /report
│   └── admin.py      ← admin commands
├── requirements.txt
├── Procfile          ← Heroku
├── runtime.txt       ← Heroku Python version
├── render.yaml       ← Render
└── .env.example
```

---

## ⚙️ Configuration

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | ✅ | Comma-separated numeric Telegram IDs (get yours from [@userinfobot](https://t.me/userinfobot)) |
| `DB_PATH` | ❌ | Database file, default `data/db.json` |

Everything else (limits, interests list, daily bonus, support link) is in `config.py`.

> The bot sets its own command menu on startup, so BotFather `/setcommands` is optional.

---

## 💻 Run locally

```bash
git clone <your-repo-url> stranger-chaos && cd stranger-chaos
python3 -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env: BOT_TOKEN and ADMIN_IDS
python bot.py
```

Stop with `Ctrl+C`.

---

## 🖥 Deploy on a VPS (recommended)

A VPS keeps `data/db.json` on a real disk, so users, premium and bans survive restarts. Steps for Ubuntu/Debian (22.04+).

### 1. Prepare the server
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
sudo adduser --disabled-password --gecos "" botuser
sudo su - botuser
```

### 2. Get the code and install
```bash
git clone <your-repo-url> stranger-chaos && cd stranger-chaos
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env      # fill in BOT_TOKEN and ADMIN_IDS
exit                                    # back to your sudo user
```

### 3. Run it as a service (auto-start + auto-restart)
Create `/etc/systemd/system/stranger-chaos.service`:
```ini
[Unit]
Description=Stranger Chaos Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
User=botuser
WorkingDirectory=/home/botuser/stranger-chaos
ExecStart=/home/botuser/stranger-chaos/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stranger-chaos
sudo systemctl status stranger-chaos        # should say "active (running)"
```

### 4. Everyday commands
```bash
journalctl -u stranger-chaos -f             # live logs
sudo systemctl restart stranger-chaos       # restart
```

### 5. Update to a new version
```bash
sudo su - botuser
cd stranger-chaos && git pull
./venv/bin/pip install -r requirements.txt
exit
sudo systemctl restart stranger-chaos
```

### 6. Back up your data
```bash
cp /home/botuser/stranger-chaos/data/db.json ~/db-backup-$(date +%F).json
```
(Run it from cron for automatic daily backups.)

**Quick alternative with `screen`:** `screen -S bot`, `./venv/bin/python bot.py`, detach with `Ctrl+A` then `D`. It won't restart after a reboot, so systemd is better.

---

## ☁️ Deploy on Heroku

The bot uses long polling, so it runs as a **worker** dyno (no web port needed). The repo already contains `Procfile` and `runtime.txt`.

### ⚠️ Read first: data persistence
Heroku's filesystem is **ephemeral**: the dyno restarts at least once a day and `data/db.json` is wiped each time (users must re-register, premium and bans are lost). Heroku is fine for testing. For production either use the VPS route above, or replace `database.py` with a Postgres version (Heroku Postgres add-on). Every other file only talks to `database.py`.

### 1. Install the CLI and log in
```bash
# https://devcenter.heroku.com/articles/heroku-cli
heroku login
```

### 2. Create the app
```bash
cd stranger-chaos
git init && git add . && git commit -m "Stranger Chaos bot"     # skip if already a git repo
heroku create your-app-name
```

### 3. Set config vars
```bash
heroku config:set BOT_TOKEN=123456:ABC-your-token ADMIN_IDS=123456789
```

### 4. Deploy
```bash
git push heroku main          # use `master` if that is your branch name
```

### 5. Turn on the worker (and make sure no web dyno runs)
```bash
heroku ps:scale worker=1 web=0
heroku logs --tail            # look for "Stranger Chaos Bot starting as @yourbot"
```

### Dashboard alternative
Heroku Dashboard → **New → Create new app** → **Deploy** tab → connect GitHub → **Deploy Branch**. Then **Settings → Reveal Config Vars** to add `BOT_TOKEN` and `ADMIN_IDS`, and on the **Resources** tab switch the `worker` dyno on and `web` off.

### Update later
```bash
git add . && git commit -m "update" && git push heroku main
```

---

## 🚀 Deploy on Render
1. Push the repo to GitHub.
2. [render.com](https://render.com) → New → **Background Worker** → connect the repo (it reads `render.yaml`).
3. Set `BOT_TOKEN` and `ADMIN_IDS` in the dashboard and deploy.

Same persistence caveat as Heroku: attach a persistent disk and point `DB_PATH` at it.

---

## 🛡 Admin Commands

| Command | Description |
|---|---|
| `/stats` | Bot statistics |
| `/userinfo <id>` | Show a user's record |
| `/ban <id> [reason]` | Ban a user |
| `/unban <id>` | Unban a user |
| `/premium <id>` | Grant premium |
| `/unpremium <id>` | Revoke premium |
| `/addcoin <id> <n>` | Add bonus searches |
| `/broadcast <msg>` | Message all users |
| `/reports` | List open reports (with Resolve / Ban buttons) |
| `/resolve <n>` | Resolve report #n |

New reports are also DM'd to every admin automatically. Admins must press **Start** on the bot once to receive them.

---

## 👤 User Commands

| Command | Description |
|---|---|
| `/search`, `» Next` | Find a stranger / skip to a new one |
| `/stop` | End the chat or stop searching |
| `/icebreaker` | Send a conversation starter to both people |
| `/interests` | Pick up to 5 interests for better matches |
| `/daily` | Claim bonus searches (streak grows each day) |
| `/profile` | View / edit age, gender, country, interests |
| `/link` | Send your Telegram profile link to your partner |
| `/block`, `/blocklist`, `/unblock <n>` | Block management (premium) |
| `/del` | Reply to your own message to delete it for both sides (premium) |
| `/report <reason>` | Report your partner |

---

## 🗄 Swapping the Database
`database.py` is the only file that touches storage. Replace it with SQLite, PostgreSQL or Redis and keep the same async function names; the rest of the bot doesn't change.

## 🛠 Troubleshooting
- **`Set BOT_TOKEN ...` on start** — the env var / `.env` is missing or still the placeholder.
- **Bot silent after deploy** — check logs; make sure only one copy of the bot is running (two instances with the same token cause `TelegramConflictError`).
- **Admin report alerts don't arrive** — the admin hasn't pressed Start on the bot, or `ADMIN_IDS` is wrong.

---

Made with ❤️ using [aiogram 3](https://docs.aiogram.dev/)
