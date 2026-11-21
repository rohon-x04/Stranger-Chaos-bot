"""
JSON-backed database.

Upgrades over the first version:
  * data is loaded once and cached in memory (no full-file read per call)
  * writes are atomic (temp file + os.replace) so a crash can't corrupt the DB
  * try_pair() pairs two users atomically (no double-matching races)
  * reports have stable ids; interests + daily-bonus fields added

Swap _load / _save for SQLite or Redis without changing any plugin code.
"""

import asyncio
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import config
from config import DB_PATH

_lock = asyncio.Lock()
_cache: Optional[dict] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        "interests": [],      # list of keys from config.INTERESTS
        "registered": False,
        # searches
        "searches_used_today": 0,
        "searches_date": str(date.today()),
        "bonus_searches": 0,  # extra searches from likes / daily bonus
        # daily bonus
        "last_daily": None,   # ISO date of last claim
        "daily_streak": 0,
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


def _empty_db() -> dict:
    return {"users": {}, "waiting": [], "pairs": {}, "reports": []}


def _normalise(data: dict) -> dict:
    """Fill in anything an older db.json might be missing."""
    for k, v in _empty_db().items():
        data.setdefault(k, v)
    # waiting entries: old format allowed bare ints
    data["waiting"] = [
        e if isinstance(e, dict) else {"id": e, "want": None} for e in data["waiting"]
    ]
    # reports: give legacy reports a stable id
    nxt = max([r.get("id", 0) for r in data["reports"]] + [0]) + 1
    for r in data["reports"]:
        if "id" not in r:
            r["id"] = nxt
            nxt += 1
    # users: backfill new fields
    base = _default_user(0)
    for u in data["users"].values():
        for k, v in base.items():
            u.setdefault(k, v if not isinstance(v, list) else [])
    return data


def _db() -> dict:
    """In-memory database (loaded from disk on first use). Call under _lock."""
    global _cache
    if _cache is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        if Path(DB_PATH).exists():
            with open(DB_PATH, "r", encoding="utf-8") as f:
                _cache = _normalise(json.load(f))
        else:
            _cache = _empty_db()
    return _cache


def _save():
    """Atomic write of the cache to disk."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{DB_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, DB_PATH)


def _reset_daily_if_needed(u: dict) -> dict:
    today = str(date.today())
    if u.get("searches_date") != today:
        u["searches_used_today"] = 0
        u["searches_date"] = today
    return u


def _available(u: dict) -> int:
    daily = config.PREMIUM_DAILY_SEARCHES if u.get("premium") else config.FREE_DAILY_SEARCHES
    return max(0, daily - u.get("searches_used_today", 0) + u.get("bonus_searches", 0))


# ── User CRUD ─────────────────────────────────────────────────────────────────

async def ensure_user(uid: int, uname: str = "", fname: str = "") -> dict:
    async with _lock:
        db = _db()
        key = str(uid)
        u = db["users"].get(key)
        if u is None:
            u = _default_user(uid, uname, fname)
            u["joined"] = _now()
            db["users"][key] = u
            _save()
        elif (uname and u.get("username") != uname) or (fname and u.get("first_name") != fname):
            u["username"] = uname or u.get("username", "")
            u["first_name"] = fname or u.get("first_name", "")
            _save()
        return dict(u)


async def get_user(uid: int) -> Optional[dict]:
    async with _lock:
        u = _db()["users"].get(str(uid))
        return dict(u) if u else None


async def update_user(uid: int, **kwargs):
    async with _lock:
        u = _db()["users"].get(str(uid))
        if u is not None:
            u.update(kwargs)
            _save()


async def all_users() -> list[dict]:
    async with _lock:
        return [dict(u) for u in _db()["users"].values()]


# ── Search balance ────────────────────────────────────────────────────────────

async def searches_left(uid: int) -> int:
    async with _lock:
        u = _db()["users"].get(str(uid))
        if not u:
            return 0
        _reset_daily_if_needed(u)
        return _available(u)


async def consume_search(uid: int) -> bool:
    """Returns True if a search was consumed, False if none left."""
    async with _lock:
        u = _db()["users"].get(str(uid))
        if not u:
            return False
        _reset_daily_if_needed(u)
        if _available(u) <= 0:
            return False
        if u.get("bonus_searches", 0) > 0:
            u["bonus_searches"] -= 1
        else:
            u["searches_used_today"] = u.get("searches_used_today", 0) + 1
        _save()
        return True


async def add_bonus_searches(uid: int, amount: int):
    async with _lock:
        u = _db()["users"].get(str(uid))
        if u is not None:
            u["bonus_searches"] = max(0, u.get("bonus_searches", 0) + amount)
            _save()


async def remove_bonus_searches(uid: int, amount: int):
    await add_bonus_searches(uid, -amount)


# ── Daily bonus (NEW) ─────────────────────────────────────────────────────────

async def claim_daily(uid: int) -> dict:
    """
    Returns {"ok": bool, "amount": int, "streak": int}.
    ok=False means already claimed today (amount=0).
    """
    async with _lock:
        u = _db()["users"].get(str(uid))
        if not u:
            return {"ok": False, "amount": 0, "streak": 0}
        today = date.today()
        last = u.get("last_daily")
        if last == str(today):
            return {"ok": False, "amount": 0, "streak": u.get("daily_streak", 0)}
        yesterday = str(today - timedelta(days=1))
        streak = u.get("daily_streak", 0) + 1 if last == yesterday else 1
        amount = min(
            config.DAILY_BONUS_BASE + config.DAILY_BONUS_STEP * (streak - 1),
            config.DAILY_BONUS_MAX,
        )
        u["last_daily"] = str(today)
        u["daily_streak"] = streak
        u["bonus_searches"] = u.get("bonus_searches", 0) + amount
        _save()
        return {"ok": True, "amount": amount, "streak": streak}


# ── Interests (NEW) ───────────────────────────────────────────────────────────

async def get_interests(uid: int) -> list[str]:
    u = await get_user(uid)
    return list(u.get("interests", [])) if u else []


async def toggle_interest(uid: int, key: str) -> str:
    """Returns 'added' | 'removed' | 'limit' | 'invalid'."""
    if key not in config.INTERESTS:
        return "invalid"
    async with _lock:
        u = _db()["users"].get(str(uid))
        if not u:
            return "invalid"
        cur = u.setdefault("interests", [])
        if key in cur:
            cur.remove(key)
            result = "removed"
        elif len(cur) >= config.MAX_INTERESTS:
            return "limit"
        else:
            cur.append(key)
            result = "added"
        _save()
        return result


async def clear_interests(uid: int):
    await update_user(uid, interests=[])


# ── Queue ─────────────────────────────────────────────────────────────────────

async def add_waiting(uid: int, gender_filter: Optional[str] = None):
    """gender_filter: 'male' | 'female' | None"""
    async with _lock:
        db = _db()
        if any(e["id"] == uid for e in db["waiting"]):
            return
        db["waiting"].append({"id": uid, "want": gender_filter})
        _save()


async def remove_waiting(uid: int):
    async with _lock:
        db = _db()
        before = len(db["waiting"])
        db["waiting"] = [e for e in db["waiting"] if e["id"] != uid]
        if len(db["waiting"]) != before:
            _save()


async def get_waiting() -> list[dict]:
    """Returns list of dicts: {id, want} (oldest first)."""
    async with _lock:
        return [dict(e) for e in _db()["waiting"]]


async def is_waiting(uid: int) -> bool:
    async with _lock:
        return any(e["id"] == uid for e in _db()["waiting"])


# ── Pairs ─────────────────────────────────────────────────────────────────────

async def try_pair(a: int, b: int) -> bool:
    """
    Atomically pair a and b. Succeeds only if both are still waiting and
    neither is already in a chat. Removes both from the queue.
    """
    async with _lock:
        db = _db()
        waiting_ids = {e["id"] for e in db["waiting"]}
        if a not in waiting_ids or b not in waiting_ids:
            return False
        if str(a) in db["pairs"] or str(b) in db["pairs"]:
            return False
        db["waiting"] = [e for e in db["waiting"] if e["id"] not in (a, b)]
        db["pairs"][str(a)] = b
        db["pairs"][str(b)] = a
        for uid in (a, b):
            u = db["users"].get(str(uid))
            if u is not None:
                u["total_chats"] = u.get("total_chats", 0) + 1
        _save()
        return True


async def get_partner(uid: int) -> Optional[int]:
    async with _lock:
        v = _db()["pairs"].get(str(uid))
        return int(v) if v is not None else None


async def remove_pair(uid: int) -> Optional[int]:
    async with _lock:
        db = _db()
        partner = db["pairs"].pop(str(uid), None)
        if partner is not None:
            db["pairs"].pop(str(int(partner)), None)
            _save()
        return int(partner) if partner is not None else None


async def is_in_chat(uid: int) -> bool:
    async with _lock:
        return str(uid) in _db()["pairs"]


# ── Block list ────────────────────────────────────────────────────────────────

async def block_user(blocker: int, target: int) -> str:
    if blocker == target:
        return "self"
    async with _lock:
        u = _db()["users"].get(str(blocker))
        if u is None:
            return "self"
        bl = u.setdefault("blocked", [])
        if target in bl:
            return "already"
        if len(bl) >= config.MAX_BLOCK_LIST:
            return "limit"
        bl.append(target)
        _save()
        return "ok"


async def unblock_by_index(blocker: int, idx_1based: int) -> str:
    async with _lock:
        u = _db()["users"].get(str(blocker))
        bl = u.get("blocked", []) if u else []
        idx = idx_1based - 1
        if idx < 0 or idx >= len(bl):
            return "not_found"
        bl.pop(idx)
        _save()
        return "ok"


async def get_blocklist(uid: int) -> list[int]:
    async with _lock:
        u = _db()["users"].get(str(uid))
        return list(u.get("blocked", [])) if u else []


async def is_blocked_by(blocker: int, target: int) -> bool:
    return target in await get_blocklist(blocker)


# ── Rating ────────────────────────────────────────────────────────────────────

async def apply_like(rater: int, target: int):
    async with _lock:
        u = _db()["users"].get(str(target))
        if u is not None:
            u["bonus_searches"] = u.get("bonus_searches", 0) + config.LIKE_REWARD
            u["likes"] = u.get("likes", 0) + 1
            _save()


async def apply_dislike(rater: int, target: int):
    async with _lock:
        u = _db()["users"].get(str(target))
        if u is not None:
            u["bonus_searches"] = max(0, u.get("bonus_searches", 0) - config.DISLIKE_COST)
            u["dislikes"] = u.get("dislikes", 0) + 1
            _save()


# ── Reports ───────────────────────────────────────────────────────────────────

async def add_report(reporter: int, reported: int, reason: str) -> dict:
    async with _lock:
        db = _db()
        rid = max([r["id"] for r in db["reports"]] + [0]) + 1
        report = {
            "id": rid,
            "reporter": reporter,
            "reported": reported,
            "reason": reason,
            "time": _now(),
            "resolved": False,
        }
        db["reports"].append(report)
        _save()
        return dict(report)


async def get_reports(resolved: bool = False) -> list[dict]:
    async with _lock:
        return [dict(r) for r in _db()["reports"] if bool(r.get("resolved")) == resolved]


async def resolve_report(report_id: int) -> bool:
    async with _lock:
        for r in _db()["reports"]:
            if r["id"] == report_id:
                r["resolved"] = True
                _save()
                return True
        return False


async def count_open_reports_against(uid: int) -> int:
    async with _lock:
        return sum(
            1 for r in _db()["reports"]
            if r["reported"] == uid and not r.get("resolved")
        )


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
        db = _db()
        users = db["users"]
        reports = db["reports"]
        return {
            "total_users": len(users),
            "active_chats": len(db["pairs"]) // 2,
            "waiting": len(db["waiting"]),
            "total_reports": len(reports),
            "open_reports": sum(1 for r in reports if not r.get("resolved")),
            "banned": sum(1 for u in users.values() if u.get("banned")),
            "premium": sum(1 for u in users.values() if u.get("premium")),
            "registered": sum(1 for u in users.values() if u.get("registered")),
        }
