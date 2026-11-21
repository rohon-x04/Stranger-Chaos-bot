"""Pure matching logic (no Telegram / DB access)."""

from typing import Optional


def shared_interests(a: list[str], b: list[str]) -> list[str]:
    bs = set(b)
    return list(dict.fromkeys(x for x in a if x in bs))


def compatible(me: dict, my_want: Optional[str], cand: dict, cand_want: Optional[str]) -> bool:
    if my_want and cand.get("gender") != my_want:
        return False
    if cand_want and me.get("gender") != cand_want:
        return False
    return True


def pick_best(me: dict, candidates: list[dict]) -> Optional[dict]:
    if not candidates:
        return None
    my_int = me.get("interests") or []
    return max(candidates, key=lambda c: len(shared_interests(my_int, c.get("interests") or [])))
