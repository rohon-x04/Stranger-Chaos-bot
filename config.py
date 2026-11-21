"""Configuration for Stranger Chaos Bot."""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE").strip()

raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = []
for value in raw_admin_ids.split(","):
    value = value.strip()
    if value.isdigit():
        ADMIN_IDS.append(int(value))

BOT_NAME = "Stranger Chaos"
SUPPORT_LINK = "https://t.me/stranger_chaos_support"

FREE_DAILY_SEARCHES = 100
PREMIUM_DAILY_SEARCHES = 200
MAX_BLOCK_LIST = 30
MIN_AGE = 18
MAX_AGE = 80

LIKE_REWARD = 1
DISLIKE_COST = 1

MAX_INTERESTS = 5
INTERESTS: dict[str, str] = {
    "music": "🎵 Music", "gaming": "🎮 Gaming", "movies": "🎬 Movies",
    "anime": "🍥 Anime", "sports": "⚽ Sports", "coding": "💻 Coding",
    "travel": "✈️ Travel", "books": "📚 Books", "memes": "😂 Memes",
    "fitness": "💪 Fitness", "food": "🍕 Food", "art": "🎨 Art",
}

DAILY_BONUS_BASE = 3
DAILY_BONUS_STEP = 1
DAILY_BONUS_MAX = 10
ICEBREAKER_COOLDOWN = 20
NOTIFY_ADMINS_ON_REPORT = True
PREMIUM_ENABLED = True
DB_PATH: str = os.getenv("DB_PATH", "data/db.json")
