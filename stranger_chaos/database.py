"""
JSON-backed database.
Swap _load / _save for SQLite or Redis without changing any plugin code.
"""

import json
import asyncio
from pathlib import Path
from datetime import date
from typing import Optional

from config import DB_PATH, FREE_DAILY_SEARCHES

_lock = asyncio.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_user(uid: int, uname: str = "", fname: str = "") -> dict:
    return {
        "id": uid,
        "username": uname,
        "first_name": fname,
        # profile
        "age": None,
        "gender": None,       # "male" | "female"
        "country": None,
        "registered": False,
        # searches
        "searches_used_today": 0,
        "searches_date": str(date.today()),
        "bonus_searches": 0,  # extra searches from likes
        # premium
        "premium": False,
        # relations
        "blocked": [],        # list of user_ids
        # stats
        "likes": 0,
        "dislikes": 0,
        "total_chats": 0,
        # moderation
        "banned": False,
        "ban_reason": "",
        # meta
        "joined": None,
    }


def _load() -> dict:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    if not Path(DB_PATH).exists():
        return {"users": {}, "waiting": [], "pairs": {}, "reports": []}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _reset_daily_if_needed(u: dict) -> dict:
    """Reset daily search counter if it's a new day."""
    today = str(date.today())
    if u.get("searches_date") != today:
        u["searches_used_today"] = 0
        u["searches_date"] = today
    return u


# ── User CRUD ─────────────────────────────────────────────────────────────────

async def ensure_user(uid: int, uname: str = "", fname: str = "") -> dict:
    async with _lock:
        db = _load()
        key = str(uid)
        if key not in db["users"]:
            from datetime import datetime
            u = _default_user(uid, uname, fname)
            u["joined"] = datetime.utcnow().isoformat()
            db["users"][key] = u
            _save(db)
        else:
            if uname:
                db["users"][key]["username"] = uname
            if fname:
                db["users"][key]["first_name"] = fname
            _save(db)
        return dict(db["users"][key])


async def get_user(uid: int) -> Optional[dict]:
    async with _lock:
        db = _load()
        u = db["users"].get(str(uid))
        return dict(u) if u else None


async def update_user(uid: int, **kwargs):
    async with _lock:
        db = _load()
        key = str(uid)
        if key in db["users"]:
            db["users"][key].update(kwargs)
            _save(db)


async def all_users() -> list[dict]:
    async with _lock:
        db = _load()
        return [dict(u) for u in db["users"].values()]


# ── Search balance ────────────────────────────────────────────────────────────

async def searches_left(uid: int) -> int:
    from config import FREE_DAILY_SEARCHES, PREMIUM_DAILY_SEARCHES, PREMIUM_ENABLED
    async with _lock:
        db = _load()
        key = str(uid)
        u = db["users"].get(key)
        if not u:
            return 0
        u = _reset_daily_if_needed(u)
        db["users"][key] = u
        _save(db)

        daily = PREMIUM_DAILY_SEARCHES if u.get("premium") else FREE_DAILY_SEARCHES
        used = u.get("searches_used_today", 0)
        bonus = u.get("bonus_searches", 0)
        return max(0, daily - used + bonus)


async def consume_search(uid: int) -> bool:
    """Returns True if search was consumed, False if none left."""
    from config import FREE_DAILY_SEARCHES, PREMIUM_DAILY_SEARCHES
    async with _lock:
        db = _load()
        key = str(uid)
        u = db["users"].get(key)
        if not u:
            return False
        u = _reset_daily_if_needed(u)

        daily = PREMIUM_DAILY_SEARCHES if u.get("premium") else FREE_DAILY_SEARCHES
        used = u.get("searches_used_today", 0)
        bonus = u.get("bonus_searches", 0)
        available = daily - used + bonus

        if available <= 0:
            db["users"][key] = u
            _save(db)
            return False

        # Consume from bonus first
        if bonus > 0:
            u["bonus_searches"] = max(0, bonus - 1)
        else:
            u["searches_used_today"] = used + 1

        db["users"][key] = u
        _save(db)
        return True


async def add_bonus_searches(uid: int, amount: int):
    async with _lock:
        db = _load()
        key = str(uid)
        if key in db["users"]:
            db["users"][key]["bonus_searches"] = db["users"][key].get("bonus_searches", 0) + amount
            _save(db)


async def remove_bonus_searches(uid: int, amount: int):
    async with _lock:
        db = _load()
        key = str(uid)
        if key in db["users"]:
            cur = db["users"][key].get("bonus_searches", 0)
            db["users"][key]["bonus_searches"] = max(0, cur - amount)
            _save(db)


# ── Queue ─────────────────────────────────────────────────────────────────────

async def add_waiting(uid: int, gender_filter: Optional[str] = None):
    """gender_filter: 'male' | 'female' | None"""
    async with _lock:
        db = _load()
        # Store as dict to carry gender preference
        for entry in db["waiting"]:
            if isinstance(entry, dict) and entry.get("id") == uid:
                return
            if entry == uid:
                return
        db["waiting"].append({"id": uid, "want": gender_filter})
        _save(db)


async def remove_waiting(uid: int):
    async with _lock:
        db = _load()
        db["waiting"] = [
            e for e in db["waiting"]
            if not (isinstance(e, dict) and e.get("id") == uid) and e != uid
        ]
        _save(db)


async def get_waiting() -> list[dict]:
    """Returns list of dicts: {id, want}"""
    async with _lock:
        db = _load()
        result = []
        for e in db["waiting"]:
            if isinstance(e, dict):
                result.append(e)
            else:
                result.append({"id": e, "want": None})
        return result


async def is_waiting(uid: int) -> bool:
    entries = await get_waiting()
    return any(e["id"] == uid for e in entries)


# ── Pairs ─────────────────────────────────────────────────────────────────────

async def create_pair(a: int, b: int):
    async with _lock:
        db = _load()
        db["pairs"][str(a)] = b
        db["pairs"][str(b)] = a
        _save(db)


async def get_partner(uid: int) -> Optional[int]:
    async with _lock:
        db = _load()
        v = db["pairs"].get(str(uid))
        return int(v) if v is not None else None


async def remove_pair(uid: int) -> Optional[int]:
    async with _lock:
        db = _load()
        partner = db["pairs"].pop(str(uid), None)
        if partner is not None:
            db["pairs"].pop(str(int(partner)), None)
        _save(db)
        return int(partner) if partner is not None else None


async def is_in_chat(uid: int) -> bool:
    async with _lock:
        db = _load()
        return str(uid) in db["pairs"]


# ── Block list ────────────────────────────────────────────────────────────────

async def block_user(blocker: int, target: int) -> str:
    if blocker == target:
        return "self"
    async with _lock:
        from config import MAX_BLOCK_LIST
        db = _load()
        key = str(blocker)
        bl = db["users"].get(key, {}).get("blocked", [])
        if target in bl:
            return "already"
        if len(bl) >= MAX_BLOCK_LIST:
            return "limit"
        bl.append(target)
        db["users"][key]["blocked"] = bl
        _save(db)
        return "ok"


async def unblock_by_index(blocker: int, idx_1based: int) -> str:
    async with _lock:
        db = _load()
        key = str(blocker)
        bl = db["users"].get(key, {}).get("blocked", [])
        idx = idx_1based - 1
        if idx < 0 or idx >= len(bl):
            return "not_found"
        bl.pop(idx)
        db["users"][key]["blocked"] = bl
        _save(db)
        return "ok"


async def get_blocklist(uid: int) -> list[int]:
    async with _lock:
        db = _load()
        return list(db["users"].get(str(uid), {}).get("blocked", []))


async def is_blocked_by(blocker: int, target: int) -> bool:
    bl = await get_blocklist(blocker)
    return target in bl


# ── Rating ────────────────────────────────────────────────────────────────────

async def apply_like(rater: int, target: int):
    from config import LIKE_REWARD
    async with _lock:
        db = _load()
        tkey = str(target)
        if tkey in db["users"]:
            db["users"][tkey]["bonus_searches"] = db["users"][tkey].get("bonus_searches", 0) + LIKE_REWARD
            db["users"][tkey]["likes"] = db["users"][tkey].get("likes", 0) + 1
        _save(db)


async def apply_dislike(rater: int, target: int):
    from config import DISLIKE_COST
    async with _lock:
        db = _load()
        tkey = str(target)
        if tkey in db["users"]:
            cur = db["users"][tkey].get("bonus_searches", 0)
            db["users"][tkey]["bonus_searches"] = max(0, cur - DISLIKE_COST)
            db["users"][tkey]["dislikes"] = db["users"][tkey].get("dislikes", 0) + 1
        _save(db)


# ── Reports ───────────────────────────────────────────────────────────────────

async def add_report(reporter: int, reported: int, reason: str):
    async with _lock:
        from datetime import datetime
        db = _load()
        db["reports"].append({
            "reporter": reporter,
            "reported": reported,
            "reason": reason,
            "time": datetime.utcnow().isoformat(),
            "resolved": False,
        })
        _save(db)


async def get_reports(resolved: bool = False) -> list[dict]:
    async with _lock:
        db = _load()
        return [r for r in db["reports"] if r.get("resolved") == resolved]


async def resolve_report(index: int):
    async with _lock:
        db = _load()
        if 0 <= index < len(db["reports"]):
            db["reports"][index]["resolved"] = True
            _save(db)


# ── Ban ───────────────────────────────────────────────────────────────────────

async def ban_user(uid: int, reason: str = "Violation of rules"):
    await update_user(uid, banned=True, ban_reason=reason)


async def unban_user(uid: int):
    await update_user(uid, banned=False, ban_reason="")


async def is_banned(uid: int) -> bool:
    u = await get_user(uid)
    return bool(u and u.get("banned"))


# ── Stats ─────────────────────────────────────────────────────────────────────

async def stats() -> dict:
    async with _lock:
        db = _load()
        users = db["users"]
        pairs = db["pairs"]
        waiting = db["waiting"]
        reports = db["reports"]
        return {
            "total_users": len(users),
            "active_chats": len(pairs) // 2,
            "waiting": len(waiting),
            "total_reports": len(reports),
            "open_reports": sum(1 for r in reports if not r.get("resolved")),
            "banned": sum(1 for u in users.values() if u.get("banned")),
            "premium": sum(1 for u in users.values() if u.get("premium")),
            "registered": sum(1 for u in users.values() if u.get("registered")),
        }
