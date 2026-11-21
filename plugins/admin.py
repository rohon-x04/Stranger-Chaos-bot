"""
Admin commands (ADMIN_IDS only):
  /stats             — bot stats
  /ban <id> [reason] — ban user
  /unban <id>        — unban
  /premium <id>      — grant premium
  /unpremium <id>    — revoke premium
  /addcoin <id> <n>  — add bonus searches
  /broadcast <msg>   — message all users
  /reports           — open reports with action buttons
  /resolve <n>       — resolve report #n
  /userinfo <id>     — show user record
"""

import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

import database as db
import texts
import keyboards
from config import ADMIN_IDS
from utils import esc

logger = logging.getLogger(__name__)
router = Router()


def _adm(uid: int) -> bool:
    return uid in ADMIN_IDS


# ── /stats ────────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    s = await db.stats()
    await message.answer(texts.ADMIN_STATS.format(**s))


# ── /ban / /unban ─────────────────────────────────────────────────────────────

@router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer("Usage: <code>/ban &lt;id&gt; [reason]</code>")
        return
    tid = int(parts[1])
    reason = parts[2].strip() if len(parts) > 2 else "Violation of rules"
    await db.ban_user(tid, reason)
    partner_id = await db.remove_pair(tid)
    await db.remove_waiting(tid)
    await message.answer(f"\U0001f6ab Banned <code>{tid}</code>. Reason: <i>{esc(reason)}</i>")
    try:
        await bot.send_message(tid, texts.BANNED.format(reason=esc(reason)))
    except Exception:
        pass
    if partner_id:
        try:
            await bot.send_message(partner_id, texts.CHAT_ENDED_PARTNER, reply_markup=keyboards.main_menu())
        except Exception:
            pass


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer("Usage: <code>/unban &lt;id&gt;</code>")
        return
    await db.unban_user(int(parts[1]))
    await message.answer(f"\u2705 Unbanned <code>{parts[1]}</code>.")


# ── /premium / /unpremium ─────────────────────────────────────────────────────

@router.message(Command("premium"))
async def cmd_grant(message: Message, bot: Bot):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer("Usage: <code>/premium &lt;id&gt;</code>")
        return
    tid = int(parts[1])
    await db.update_user(tid, premium=True)
    await message.answer(f"\U0001f4a0 Premium granted to <code>{tid}</code>.")
    try:
        await bot.send_message(tid, texts.PREMIUM_GRANTED)
    except Exception:
        pass


@router.message(Command("unpremium"))
async def cmd_revoke(message: Message):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer("Usage: <code>/unpremium &lt;id&gt;</code>")
        return
    await db.update_user(int(parts[1]), premium=False)
    await message.answer(f"\u274c Premium revoked from <code>{parts[1]}</code>.")


# ── /addcoin ──────────────────────────────────────────────────────────────────

@router.message(Command("addcoin"))
async def cmd_addcoin(message: Message):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].strip().lstrip("-").isdigit() or not parts[2].strip().lstrip("-").isdigit():
        await message.answer("Usage: <code>/addcoin &lt;id&gt; &lt;amount&gt;</code>")
        return
    tid, amount = int(parts[1]), int(parts[2])
    await db.add_bonus_searches(tid, amount)
    u = await db.get_user(tid)
    bal = u.get("bonus_searches", 0) if u else "?"
    await message.answer(f"\U0001f4b0 Added {amount} to <code>{tid}</code>. Bonus now: <b>{bal}</b>")


# ── /broadcast ────────────────────────────────────────────────────────────────

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Usage: <code>/broadcast &lt;message&gt;</code>")
        return
    text = parts[1].strip()
    users = await db.all_users()
    sent = failed = 0
    for u in users:
        if u.get("banned"):
            continue
        try:
            await bot.send_message(u["id"], f"\U0001f4e3 <b>Announcement</b>\n\n{text}")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)   # stay under Telegram's ~30 msg/s limit
    await message.answer(texts.ADMIN_BROADCAST_DONE.format(n=sent, failed=failed))


# ── /reports / /resolve ───────────────────────────────────────────────────────

@router.message(Command("reports"))
async def cmd_reports(message: Message):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    open_r = await db.get_reports(resolved=False)
    if not open_r:
        await message.answer("\u2705 No open reports.")
        return
    for r in open_r:
        await message.answer(
            f"\U0001f6a8 <b>Report #{r['id']}</b>\n"
            f"Reporter: <code>{r['reporter']}</code>\n"
            f"Reported: <code>{r['reported']}</code>\n"
            f"Reason: <i>{esc(r['reason'])}</i>\n"
            f"Time: {r['time']}",
            reply_markup=keyboards.admin_report_btns(r["id"], r["reported"]),
        )


@router.message(Command("resolve"))
async def cmd_resolve(message: Message):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Usage: <code>/resolve &lt;report_number&gt;</code>")
        return
    ok = await db.resolve_report(int(parts[1]))
    await message.answer(
        f"\u2705 Report #{parts[1]} resolved." if ok else "\u274c No report with that number."
    )


# ── /userinfo ─────────────────────────────────────────────────────────────────

@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    if not _adm(message.from_user.id):
        await message.answer(texts.ADMIN_NOT_ADMIN)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer("Usage: <code>/userinfo &lt;id&gt;</code>")
        return
    u = await db.get_user(int(parts[1]))
    if not u:
        await message.answer("\u274c User not found.")
        return
    left = await db.searches_left(u["id"])
    await message.answer(
        f"\U0001f464 <b>User Info</b>\n\n"
        f"ID: <code>{u['id']}</code>\n"
        f"Username: @{u.get('username') or 'none'}\n"
        f"Name: {esc(u.get('first_name', ''))}\n"
        f"Age: {u.get('age', 'N/A')}\n"
        f"Gender: {u.get('gender', 'N/A')}\n"
        f"Country: {esc(u.get('country', 'N/A'))}\n"
        f"Interests: {', '.join(u.get('interests', [])) or 'none'}\n"
        f"Registered: {u.get('registered')}\n"
        f"Premium: {u.get('premium')}\n"
        f"Searches left: {left}\n"
        f"Bonus: {u.get('bonus_searches', 0)}\n"
        f"Total chats: {u.get('total_chats', 0)}\n"
        f"Likes: {u.get('likes', 0)} | Dislikes: {u.get('dislikes', 0)}\n"
        f"Banned: {u.get('banned')} — {esc(u.get('ban_reason', ''))}\n"
        f"Joined: {u.get('joined', 'N/A')}"
    )


# ── Admin inline callbacks ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_resolve:"))
async def cb_resolve(call: CallbackQuery):
    if not _adm(call.from_user.id):
        await call.answer("Not authorised.", show_alert=True)
        return
    rid = int(call.data.split(":")[1])
    await db.resolve_report(rid)
    await call.message.edit_text(call.message.text + "\n\n\u2705 Resolved", reply_markup=None)
    await call.answer("Resolved!")


@router.callback_query(F.data.startswith("admin_ban:"))
async def cb_admin_ban(call: CallbackQuery, bot: Bot):
    if not _adm(call.from_user.id):
        await call.answer("Not authorised.", show_alert=True)
        return
    _, tid_str, ridx_str = call.data.split(":")
    tid, ridx = int(tid_str), int(ridx_str)
    await db.ban_user(tid, "Reported by users")
    partner_id = await db.remove_pair(tid)
    await db.remove_waiting(tid)
    await db.resolve_report(ridx)
    await call.message.edit_text(
        call.message.text + f"\n\n\U0001f6ab User {tid} banned & resolved.", reply_markup=None
    )
    await call.answer("Banned!")
    try:
        await bot.send_message(tid, texts.BANNED.format(reason="Reported by users"))
    except Exception:
        pass
    if partner_id:
        try:
            await bot.send_message(partner_id, texts.CHAT_ENDED_PARTNER, reply_markup=keyboards.main_menu())
        except Exception:
            pass
