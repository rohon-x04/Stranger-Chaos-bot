"""
Stranger Chaos Bot — Configuration
Edit values here or set matching environment variables (or a .env file).
"""

import os

try:  # optional: load .env if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Required ──────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── Admin IDs (comma-separated in env) ───────────────────────────────────────
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# ── Identity ──────────────────────────────────────────────────────────────────
BOT_NAME        = "Stranger Chaos"
SUPPORT_LINK    = "https://t.me/stranger_chaos_support"   # your support group/channel

# ── Limits ────────────────────────────────────────────────────────────────────
FREE_DAILY_SEARCHES    = 100
PREMIUM_DAILY_SEARCHES = 200
MAX_BLOCK_LIST         = 30
MIN_AGE                = 18
MAX_AGE                = 80

# ── Rating impact ─────────────────────────────────────────────────────────────
LIKE_REWARD    = 1   # extra searches given to partner on Like
DISLIKE_COST   = 1   # searches removed from partner on Dislike

# ── Interests (NEW) ───────────────────────────────────────────────────────────
# key -> label. Users pick up to MAX_INTERESTS; the matcher prefers partners
# who share the most interests (falls back to anyone, so nobody waits forever).
MAX_INTERESTS = 5
INTERESTS: dict[str, str] = {
    "music":   "\U0001f3b5 Music",
    "gaming":  "\U0001f3ae Gaming",
    "movies":  "\U0001f3ac Movies",
    "anime":   "\U0001f365 Anime",
    "sports":  "⚽ Sports",
    "coding":  "\U0001f4bb Coding",
    "travel":  "✈️ Travel",
    "books":   "\U0001f4da Books",
    "memes":   "\U0001f602 Memes",
    "fitness": "\U0001f4aa Fitness",
    "food":    "\U0001f355 Food",
    "art":     "\U0001f3a8 Art",
}

# ── Daily bonus (NEW) ─────────────────────────────────────────────────────────
DAILY_BONUS_BASE = 3    # searches on day 1
DAILY_BONUS_STEP = 1    # +1 per consecutive day
DAILY_BONUS_MAX  = 10   # cap

# ── Icebreaker (NEW) ──────────────────────────────────────────────────────────
ICEBREAKER_COOLDOWN = 20  # seconds between /icebreaker uses per user

# ── Reports ───────────────────────────────────────────────────────────────────
NOTIFY_ADMINS_ON_REPORT = True   # DM every admin when a report comes in

# ── Premium flag (set False = everyone gets premium) ─────────────────────────
PREMIUM_ENABLED = True

# ── Storage ───────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/db.json")
