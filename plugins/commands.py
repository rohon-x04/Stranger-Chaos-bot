"""
User feature commands:
  /link        — share Telegram profile link
  /block       — block current partner (premium)
  /blocklist   — view blocked list
  /unblock     — unblock by list ID
  /del         — delete for both sides (premium)
  /report      — report current partner (text flow)
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database as db
import texts
import keyboards
from config import PREMIUM_ENABLED

logger = logging.getLogger(__name__)
router = Router()


def _is_premium(u: dict) -> bool:
    if not PREMIUM_ENABLED:
        return True
    return u.get("premium", False)


# ── /link ─────────────────────────────────────────────────────────────────────

@router.message(Command("link"))
async def cmd_link(message: Message):
    uname = message.from_user.username
    if not uname:
        await message.answer(texts.LINK_NO_USERNAME)
        return
    await message.answer(texts.LINK_OK.format(username=uname))


# ── /block ────────────────────────────────────────────────────────────────────

@router.message(Command("block"))
async def cmd_block(message: Message):
    u = await db.get_user(message.from_user.id)
    if not u:
        return
    if not _is_premium(u):
        await message.answer(texts.BLOCK_PREMIUM_ONLY)
        return
    partner_id = await db.get_partner(message.from_user.id)
    if not partner_id:
        await message.answer(texts.BLOCK_NOT_IN_CHAT)
        return
    result = await db.block_user(message.from_user.id, partner_id)
    msgs = {
        "ok": texts.BLOCK_OK,
        "already": texts.BLOCK_ALREADY,
        "limit": texts.BLOCK_LIMIT,
    }
    await message.answer(msgs.get(result, texts.BLOCK_OK))


# ── /blocklist ────────────────────────────────────────────────────────────────

@router.message(Command("blocklist"))
async def cmd_blocklist(message: Message):
    bl = await db.get_blocklist(message.from_user.id)
    if not bl:
        await message.answer(texts.BLOCKLIST_EMPTY)
        return
    rows = [texts.BLOCKLIST_ROW.format(n=i, uid=uid) for i, uid in enumerate(bl, 1)]
    await message.answer(
        texts.BLOCKLIST_HEADER + "\n".join(rows) +
        "\n\n<i>Use /unblock &lt;id&gt; to remove.</i>"
    )


# ── /unblock ──────────────────────────────────────────────────────────────────

@router.message(Command("unblock"))
async def cmd_unblock(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer(texts.UNBLOCK_USAGE)
        return
    result = await db.unblock_by_index(message.from_user.id, int(parts[1].strip()))
    await message.answer(texts.UNBLOCK_OK if result == "ok" else texts.UNBLOCK_NOT_FOUND)


# ── /del ──────────────────────────────────────────────────────────────────────

@router.message(Command("del"))
async def cmd_del(message: Message, bot: Bot):
    from plugins.chat import _last_msg

    u = await db.get_user(message.from_user.id)
    if not u or not _is_premium(u):
        await message.answer(texts.DEL_PREMIUM_ONLY)
        return
    partner_id = await db.get_partner(message.from_user.id)
    if not partner_id:
        await message.answer(texts.DEL_NOT_IN_CHAT)
        return
    if not message.reply_to_message:
        await message.answer(texts.DEL_REPLY_NEEDED)
        return

    tracked = _last_msg.get(message.from_user.id)
    if not tracked or tracked["own"] != message.reply_to_message.message_id:
        await message.answer(texts.DEL_NOT_YOUR_MSG)
        return

    try:
        await bot.delete_message(message.chat.id, tracked["own"])
        await bot.delete_message(partner_id, tracked["partner_msg"])
        await message.delete()
        await message.answer(texts.DEL_OK)
    except Exception as e:
        logger.warning("del failed: %s", e)


# ── /report (text command fallback) ───────────────────────────────────────────

@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext):
    partner_id = await db.get_partner(message.from_user.id)
    if not partner_id:
        await message.answer(texts.REPORT_NOT_IN_CHAT)
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(texts.REPORT_USAGE)
        return

    reason = parts[1].strip()[:300]
    await db.add_report(message.from_user.id, partner_id, reason)
    await message.answer(texts.REPORT_OK)
