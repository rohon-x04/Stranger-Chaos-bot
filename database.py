"""
JSON-backed database.

This module serializes access with asyncio.Lock and keeps an in-memory cache.
Writing is atomic to avoid corrupting db.json when a process is interrupted.
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


def _default_user(uid: int, uname: str = "", fname: str = "") -> dict:
    return {
        "id": uid,
        "username": uname,
        "first_name": fname,
        "age": None,
        "gender": None,
        "country": None,
        "interests": [],
        "registered": False,
        "searches_used_today": 0,
        "searches_date": str(date.today()),
        "bonus_searches": 0,
        "last_daily": None,
        "daily_streak": 0,
        "premium": False,
        "blocked": [],
        "likes": 0,
        "dislikes": 0,
        "total_chats": 0,
        "banned": False,
        "ban_reason": "",
        "joined": None,
    }


def _empty_db() -> dict:
    return {"users": {}, "waiting": [], "pairs": {}, "reports": []}


def _normalise(data: dict) -> dict:
    """Fill missing fields and migrate legacy database formats safely."""
    for k, v in _empty_db().items():
        data.setdefault(k, v)

    data["waiting"] = [
        e if isinstance(e, dict) else {"id": e, "want": None}
        for e in data["waiting"]
    ]

    # Validate waiting entries and remove duplicate ids.
    seen_waiting = set()
    clean_waiting = []
    for entry in data["waiting"]:
        uid = entry.get("id")
        if isinstance(uid, int) and uid not in seen_waiting:
            seen_waiting.add(uid)
            entry["want"] = entry.get("want") if entry.get("want") in (None, "male", "female") else None
            clean_waiting.append(entry)
    data["waiting"] = clean_waiting

    # Give legacy reports stable ids and remove malformed reports.
    reports = data.setdefault("reports", [])
    used_ids = {r.get("id") for r in reports if isinstance(r.get("id"), int)}
    next_id = max(used_ids, default=0) + 1
    clean_reports = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        if not isinstance(report.get("id"), int):
            while next_id in used_ids:
                next_id += 1
            report["id"] = next_id
            used_ids.add(next_id)
            next_id += 1
        clean_reports.append(report)
    data["reports"] = clean_reports

    base = _default_user(0)
    for u in data["users"].values():
        if not isinstance(u, dict):
            continue
        for k, v in base.items():
            u.setdefault(k, [] if isinstance(v, list) else v)
        u["blocked"] = [x for x in u.get("blocked", []) if isinstance(x, int)]
        u["interests"] = [x for x in u.get("interests", []) if x in config.INTERESTS]

    # Remove pair references that point to missing users and orphan queue entries.
    pairs = data.setdefault("pairs", {})
    clean_pairs = {}
    for uid, partner in pairs.items():
        if str(uid) in data["users"] and str(partner) in data["users"]:
            clean_pairs[str(uid)] = partner
    data["pairs"] = clean_pairs
    data["waiting"] = [e for e in data["waiting"] if str(e["id"]) in data["users"]]
    return data


def _db() -> dict:
    """In-memory database (loaded from disk on first use). Call under _lock."""
    global _cache
    if _cache is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        if Path(DB_PATH).exists():
            try:
                with open(DB_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    raise ValueError("database root must be a JSON object")
                _cache = _normalise(loaded)
            except (json.JSONDecodeError, OSError, ValueError):
                # Do not silently overwrite the original bad file.
                bad_path = f"{DB_PATH}.corrupt"
                os.replace(DB_PATH, bad_path)
                _cache = _empty_db()
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
    return max(0, int(daily) - int(u.get("searches_used_today", 0)) + int(u.get("bonus_searches", 0)))


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


async def searches_left(uid: int) -> int:
    async with _lock:
        u = _db()["users"].get(str(uid))
        if not u:
            return 0
        changed = u.get("searches_date") != str(date.today())
        _reset_daily_if_needed(u)
        if changed:
            _save()
        return _available(u)


async def consume_search(uid: int) -> bool:
    async with _lock:
        u = _db()["users"].get(str(uid))
        if not u:
            return False
        _reset_daily_if_needed(u)
        if _available(u) <= 0:
            _save()
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


async def claim_daily(uid: int) -> dict:
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
        amount = min(config.DAILY_BONUS_BASE + config.DAILY_BONUS_STEP * (streak - 1), config.DAILY_BONUS_MAX)
        u["last_daily"] = str(today)
        u["daily_streak"] = streak
        u["bonus_searches"] = u.get("bonus_searches", 0) + amount
        _save()
        return {"ok": True, "amount": amount, "streak": streak}


async def get_interests(uid: int) -> list[str]:
    u = await get_user(uid)
    return list(u.get("interests", [])) if u else []


async def toggle_interest(uid: int, key: str) -> str:
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


async def add_waiting(uid: int, gender_filter: Optional[str] = None):
    async with _lock:
        db = _db()
        if gender_filter not in (None, "male", "female"):
            gender_filter = None
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
    async with _lock:
        return [dict(e) for e in _db()["waiting"]]


async def is_waiting(uid: int) -> bool:
    async with _lock:
        return any(e["id"] == uid for e in _db()["waiting"])


async def try_pair(a: int, b: int) -> bool:
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
            db["pairs"].pop(str(partner), None)
            _save()
        return int(partner) if partner is not None else None


async def is_in_chat(uid: int) -> bool:
    async with _lock:
        return str(uid) in _db()["pairs"]


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


async def add_report(reporter: int, reported: int, reason: str) -> dict:
    async with _lock:
        db = _db()
        rid = max([r["id"] for r in db["reports"] if isinstance(r.get("id"), int)] + [0]) + 1
        report = {"id": rid, "reporter": reporter, "reported": reported, "reason": reason, "time": _now(), "resolved": False}
        db["reports"].append(report)
        _save()
        return dict(report)


async def get_reports(resolved: bool = False) -> list[dict]:
    async with _lock:
        return [dict(r) for r in _db()["reports"] if bool(r.get("resolved")) == resolved]


async def resolve_report(report_id: int) -> bool:
    async with _lock:
        for r in _db()["reports"]:
            if r.get("id") == report_id:
                r["resolved"] = True
                _save()
                return True
        return False


async def count_open_reports_against(uid: int) -> int:
    async with _lock:
        return sum(1 for r in _db()["reports"] if r.get("reported") == uid and not r.get("resolved"))


async def ban_user(uid: int, reason: str = "Violation of rules"):
    await update_user(uid, banned=True, ban_reason=reason)


async def unban_user(uid: int):
    await update_user(uid, banned=False, ban_reason="")


async def is_banned(uid: int) -> bool:
    u = await get_user(uid)
    return bool(u and u.get("banned"))


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
