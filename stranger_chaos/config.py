"""
Stranger Chaos Bot — Configuration
Edit values here or set matching environment variables.
"""

import os

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

# ── Premium flag (set False = everyone gets premium) ─────────────────────────
PREMIUM_ENABLED = True

# ── Storage ───────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/db.json")
