"""
Chat engine:
  Search / Find Girl / Find Boy / Next / Stop
  Interest-aware matching (NEW)
  Message relay for every supported content type, with reply-threading (NEW)
  /icebreaker conversation starters (NEW)
  Post-chat inline: Like, Dislike, Block user, Report user
"""

import asyncio
import logging
import random
import time

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database as db
import matching
import texts
import keyboards
from states import ReportFlow
from utils import esc, msg_map, notify_admins_of_report

logger = logging.getLogger(__name__)
router = Router()

# In-memory only — reset on restart (fine, they only guard UX)
_rated: set[tuple[int, int]] = set()      # (rater, partner) already rated
_ice_last: dict[int, float] = {}          # last /icebreaker use per user
_match_lock = asyncio.Lock()              # serialise matchmaking

RELAYABLE = {
    "text", "photo", "video", "audio", "voice",
    "document", "sticker", "animation", "video_note",
}


# ── Guard helpers ─────────────────────────────────────────────────────────────
# (banned users are already stopped by BanMiddleware)

async def _check_registered(message: Message) -> bool:
    u = await db.get_user(message.from_user.id)
    if not u or not u.get("registered"):
        await message.answer(texts.NOT_REGISTERED)
        return False
    return True


# ── Matching engine ───────────────────────────────────────────────────────────

def _names(keys: list[str]) -> str:
    return ", ".join(config.INTERESTS.get(k, k) for k in keys)


async def _try_match(uid: int, bot: Bot):
    """Find the best compatible waiting partner for uid (interest-aware)."""
    async with _match_lock:
        waiting = await db.get_waiting()
        mine = next((e for e in waiting if e["id"] == uid), None)
        if mine is None:
            return  # already matched / cancelled
        me = await db.get_user(uid)
        if not me:
            return

        eligible: list[dict] = []
        wants: dict[int, str | None] = {}
        for entry in waiting:
            cid = entry["id"]
            if cid == uid:
                continue
            if await db.is_in_chat(cid):
                await db.remove_waiting(cid)
                continue
            cu = await db.get_user(cid)
            if not cu or not cu.get("registered") or cu.get("banned"):
                await db.remove_waiting(cid)
                continue
            if await db.is_blocked_by(uid, cid) or await db.is_blocked_by(cid, uid):
                continue
            if not matching.compatible(me, mine.get("want"), cu, entry.get("want")):
                continue
            if await db.searches_left(cid) <= 0:
                await db.remove_waiting(cid)
                continue
            eligible.append(cu)
            wants[cid] = entry.get("want")

        best = matching.pick_best(me, eligible)
        if best is None:
            return  # stay in queue; the next arrival will trigger matching

        cid = best["id"]
        if not await db.try_pair(uid, cid):
            return

        # Each side pays one search now that a match really happened
        await db.consume_search(uid)
        await db.consume_search(cid)
        _rated.discard((uid, cid))
        _rated.discard((cid, uid))

    common = matching.shared_interests(me.get("interests", []), best.get("interests", []))
    common_line = (
        texts.COMMON_INTERESTS.format(names=_names(common)) if common else texts.NO_COMMON
    )
    me_badge = "\U0001f4a0 Premium" if me.get("premium") else "Normal user"
    c_badge = "\U0001f4a0 Premium" if best.get("premium") else "Normal user"

    await _safe_send(bot, uid, texts.PARTNER_FOUND.format(badge=c_badge, common=common_line))
    await _safe_send(bot, cid, texts.PARTNER_FOUND.format(badge=me_badge, common=common_line))


async def _safe_send(bot: Bot, chat_id: int, text: str, **kw) -> bool:
    try:
        await bot.send_message(chat_id, text, **kw)
        return True
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.info("send to %s failed: %s", chat_id, e)
        return False


# ── SEARCH / FIND GIRL / FIND BOY ─────────────────────────────────────────────

async def _start_search(message: Message, bot: Bot, gender_filter=None):
    uid = message.from_user.id

    if not await _check_registered(message):
        return

    # Gender search is premium
    if gender_filter:
        u = await db.get_user(uid)
        if config.PREMIUM_ENABLED and not u.get("premium"):
            await message.answer(
                texts.GENDER_SEARCH_PREMIUM.format(status="❌ Not active"),
                reply_markup=keyboards.premium_payment(),
            )
            return

    if await db.is_in_chat(uid):
        await message.answer(texts.ALREADY_IN_CHAT)
        return
    if await db.is_waiting(uid):
        await message.answer(texts.ALREADY_SEARCHING)
        return
    if await db.searches_left(uid) <= 0:
        await message.answer(texts.NO_SEARCHES_LEFT)
        return

    await db.add_waiting(uid, gender_filter)
    await message.answer(texts.SEARCHING)
    await _try_match(uid, bot)


@router.message(Command("search"))
@router.message(F.text == "» Next")
async def cmd_search(message: Message, bot: Bot):
    # "Next" when in a chat = skip to a new partner
    if await db.is_in_chat(message.from_user.id):
        await cmd_next(message, bot)
        return
    await _start_search(message, bot, gender_filter=None)


@router.message(F.text == "\U0001f467 Find Girl")
async def cmd_find_girl(message: Message, bot: Bot):
    if await db.is_in_chat(message.from_user.id):
        await cmd_next(message, bot)
        return
    await _start_search(message, bot, gender_filter="female")


@router.message(F.text == "\U0001f466 Find Boy")
async def cmd_find_boy(message: Message, bot: Bot):
    if await db.is_in_chat(message.from_user.id):
        await cmd_next(message, bot)
        return
    await _start_search(message, bot, gender_filter="male")


# ── STOP ──────────────────────────────────────────────────────────────────────

async def _end_chat(uid: int, bot: Bot):
    partner_id = await db.remove_pair(uid)
    await db.remove_waiting(uid)
    if partner_id:
        _rated.discard((uid, partner_id))
        _rated.discard((partner_id, uid))

    await _safe_send(
        bot, uid, texts.CHAT_ENDED_YOU,
        reply_markup=keyboards.post_chat(partner_id) if partner_id else keyboards.main_menu(),
    )
    if partner_id:
        await _safe_send(bot, partner_id, texts.CHAT_ENDED_PARTNER)


@router.message(Command("stop"))
@router.message(F.text == "\U0001f534 Stop")
async def cmd_stop(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if not await db.is_in_chat(uid):
        await db.remove_waiting(uid)
        await message.answer(texts.NOT_IN_CHAT, reply_markup=keyboards.main_menu())
        return
    await _end_chat(uid, bot)


# ── NEXT ──────────────────────────────────────────────────────────────────────

@router.message(Command("next"))
async def cmd_next(message: Message, bot: Bot):
    uid = message.from_user.id

    if not await _check_registered(message):
        return

    if await db.is_in_chat(uid):
        partner_id = await db.remove_pair(uid)
        if partner_id:
            _rated.discard((uid, partner_id))
            _rated.discard((partner_id, uid))
            await _safe_send(bot, partner_id, texts.CHAT_ENDED_PARTNER)

    if await db.searches_left(uid) <= 0:
        await db.remove_waiting(uid)
        await message.answer(texts.NO_SEARCHES_LEFT)
        return

    await message.answer(texts.NEXT_SEARCHING)
    await db.add_waiting(uid)
    await _try_match(uid, bot)


# ── ICEBREAKER (NEW) ──────────────────────────────────────────────────────────

@router.message(Command("icebreaker"))
async def cmd_icebreaker(message: Message, bot: Bot):
    uid = message.from_user.id
    pid = await db.get_partner(uid)
    if not pid:
        await message.answer(texts.ICEBREAKER_NOT_IN_CHAT)
        return

    wait = config.ICEBREAKER_COOLDOWN - (time.monotonic() - _ice_last.get(uid, 0))
    if wait > 0:
        await message.answer(texts.ICEBREAKER_COOLDOWN.format(sec=int(wait) + 1))
        return
    _ice_last[uid] = time.monotonic()

    text = texts.ICEBREAKER_MSG.format(q=random.choice(texts.ICEBREAKERS))
    await message.answer(text)
    await _safe_send(bot, pid, text)


# ── POST-CHAT INLINE BUTTONS ──────────────────────────────────────────────────

def _kb(*buttons: tuple[str, str]):
    nb = InlineKeyboardBuilder()
    for text, data in buttons:
        nb.button(text=text, callback_data=data)
    nb.adjust(1)
    return nb.as_markup()


@router.callback_query(F.data.startswith("rate:"))
async def cb_rate(call: CallbackQuery):
    _, action, pid_str = call.data.split(":", 2)
    partner_id = int(pid_str)
    uid = call.from_user.id

    key = (uid, partner_id)
    if key in _rated:
        await call.answer(texts.ALREADY_RATED, show_alert=True)
        return
    _rated.add(key)

    if action == "like":
        await db.apply_like(uid, partner_id)
        await call.answer(texts.RATED_LIKE, show_alert=True)
    else:
        await db.apply_dislike(uid, partner_id)
        await call.answer(texts.RATED_DISLIKE, show_alert=True)

    try:  # keep Block / Report, drop Like / Dislike
        await call.message.edit_reply_markup(reply_markup=_kb(
            ("\U0001f6ab Block user", f"post:block:{partner_id}"),
            ("\U0001f6a9 Report user", f"post:report:{partner_id}"),
        ))
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("post:block:"))
async def cb_post_block(call: CallbackQuery):
    partner_id = int(call.data.split(":")[2])
    uid = call.from_user.id

    u = await db.get_user(uid)
    if config.PREMIUM_ENABLED and (not u or not u.get("premium")):
        await call.answer(texts.BLOCK_PREMIUM_ONLY, show_alert=True)
        return

    result = await db.block_user(uid, partner_id)
    answers = {
        "ok": texts.BLOCK_OK,
        "already": texts.BLOCK_ALREADY,
        "limit": texts.BLOCK_LIMIT,
    }
    await call.answer(answers.get(result, ""), show_alert=bool(answers.get(result)))

    try:
        await call.message.edit_reply_markup(reply_markup=_kb(
            ("\U0001f6a9 Report user", f"post:report:{partner_id}"),
        ))
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("post:report:"))
async def cb_post_report_start(call: CallbackQuery, state: FSMContext):
    partner_id = int(call.data.split(":")[2])
    await state.update_data(report_target=partner_id)
    await call.message.answer(
        "\U0001f6a8 <b>Report</b>\n\nSend a brief reason (e.g. spam, harassment):"
    )
    await state.set_state(ReportFlow.reason)
    await call.answer()


@router.message(ReportFlow.reason)
async def report_reason_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target = data.get("report_target")
    reason = (message.text or "").strip()[:300]
    if not reason or not target:
        await message.answer("Please send a reason as text.")
        return

    report = await db.add_report(message.from_user.id, target, reason)
    await state.clear()
    await message.answer(texts.REPORT_OK)
    await notify_admins_of_report(bot, report)


# ── MESSAGE RELAY ─────────────────────────────────────────────────────────────
# One handler for every supported content type. copy_message keeps formatting,
# captions and media, and — unlike send_message(text) — never lets a stranger's
# text be parsed as HTML by our bot.

@router.message()
async def relay(message: Message, bot: Bot):
    uid = message.from_user.id
    pid = await db.get_partner(uid)
    if not pid:
        return  # not chatting — ignore

    if message.text and message.text.startswith("/"):
        return  # unknown command, don't leak it to the stranger

    if message.content_type not in RELAYABLE:
        await message.answer(texts.UNSUPPORTED)
        return

    reply_to = None
    if message.reply_to_message:
        tgt = msg_map.reply_target(uid, message.reply_to_message.message_id)
        if tgt and tgt[0] == pid:
            reply_to = tgt[1]

    try:
        sent = await bot.copy_message(
            chat_id=pid,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_to_message_id=reply_to,
            allow_sending_without_reply=True,
        )
        msg_map.record(uid, message.message_id, pid, sent.message_id)
    except TelegramForbiddenError:
        # Partner blocked / deleted the bot — end the chat cleanly
        await db.remove_pair(uid)
        await message.answer(texts.PARTNER_LEFT_BOT, reply_markup=keyboards.main_menu())
    except Exception as e:
        logger.warning("relay failed (%s -> %s): %s", uid, pid, e)
