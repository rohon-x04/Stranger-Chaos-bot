"""Pure matching logic (no Telegram / DB access) so it is easy to test."""

from typing import Optional


def shared_interests(a: list[str], b: list[str]) -> list[str]:
    """Interests in common, in the order of `a`."""
    bs = set(b)
    return [x for x in a if x in bs]


def compatible(me: dict, my_want: Optional[str], cand: dict, cand_want: Optional[str]) -> bool:
    """Gender filters must be satisfied in both directions."""
    if my_want and cand.get("gender") != my_want:
        return False
    if cand_want and me.get("gender") != cand_want:
        return False
    return True


def pick_best(me: dict, candidates: list[dict]) -> Optional[dict]:
    """
    candidates: list of user dicts (already filtered for compatibility), oldest
    waiting first. Returns the one sharing the most interests with `me`; ties
    go to whoever has waited longest. With no shared interests anywhere this is
    plain first-come-first-served, so nobody is left waiting for a perfect match.
    """
    best, best_score = None, -1
    my_int = me.get("interests", [])
    for c in candidates:
        score = len(shared_interests(my_int, c.get("interests", [])))
        if score > best_score:
            best, best_score = c, score
    return best
