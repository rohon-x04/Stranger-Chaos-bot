"""
Chat engine:
  Search / Find Girl / Find Boy / Next / Stop
  Message relay (text, photo, sticker, voice, video, doc, animation, audio, video_note)
  Post-chat inline: Like, Dislike, Block user, Report user
"""

import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database as db
import texts
import keyboards
from states import ReportFlow

logger = logging.getLogger(__name__)
router = Router()

# In-memory sets / dicts — reset on restart (fine for MVP)
_rated: set[tuple[int, int]] = set()          # (rater, partner) already rated
_last_msg: dict[int, dict] = {}               # for /del tracking


# ── Guard helpers ─────────────────────────────────────────────────────────────

async def _check_registered(message: Message) -> bool:
    u = await db.get_user(message.from_user.id)
    if not u or not u.get("registered"):
        await message.answer(texts.NOT_REGISTERED)
        return False
    return True


async def _check_banned(message: Message) -> bool:
    u = await db.get_user(message.from_user.id)
    if u and u.get("banned"):
        await message.answer(texts.BANNED.format(reason=u.get("ban_reason", "Unknown")))
        return True
    return False


# ── Matching engine ───────────────────────────────────────────────────────────

async def _try_match(uid: int, bot: Bot):
    """Find the best compatible waiting partner for uid."""
    u = await db.get_user(uid)
    if not u:
        return

    # Check search balance
    if not await db.consume_search(uid):
        await db.remove_waiting(uid)
        await bot.send_message(uid, texts.NO_SEARCHES_LEFT)
        return

    waiting = await db.get_waiting()
    waiting = [e for e in waiting if e["id"] != uid]

    # Find entry for current user (to know their gender preference)
    my_entry_list = [e for e in await db.get_waiting() if e["id"] == uid]
    my_want = my_entry_list[0]["want"] if my_entry_list else None

    for entry in waiting:
        candidate = entry["id"]
        c_want = entry.get("want")  # what this candidate wants

        # Block checks
        if await db.is_blocked_by(uid, candidate):
            continue
        if await db.is_blocked_by(candidate, uid):
            continue
        if await db.is_banned(candidate):
            await db.remove_waiting(candidate)
            continue

        cu = await db.get_user(candidate)
        if not cu or not cu.get("registered"):
            await db.remove_waiting(candidate)
            continue

        # Gender filter: my preference must match candidate's gender
        if my_want and cu.get("gender") != my_want:
            continue

        # Candidate's gender filter: candidate wants a specific gender
        if c_want and u.get("gender") != c_want:
            continue

        # Match!
        await db.remove_waiting(uid)
        await db.remove_waiting(candidate)
        await db.create_pair(uid, candidate)

        # Increment stats
        tc_u = u.get("total_chats", 0)
        tc_c = cu.get("total_chats", 0)
        await db.update_user(uid, total_chats=tc_u + 1)
        await db.update_user(candidate, total_chats=tc_c + 1)

        # Also consume search for candidate
        await db.consume_search(candidate)

        u_badge  = "\U0001f4a0 Premium" if u.get("premium") else "Normal user"
        c_badge  = "\U0001f4a0 Premium" if cu.get("premium") else "Normal user"

        await bot.send_message(uid,       texts.PARTNER_FOUND.format(badge=c_badge))
        await bot.send_message(candidate, texts.PARTNER_FOUND.format(badge=u_badge))
        return

    # No match yet — stay in queue, re-try when triggered again
    # Give back the consumed search since no match was found
    await db.add_bonus_searches(uid, 1)


# ── SEARCH / FIND GIRL / FIND BOY ─────────────────────────────────────────────

async def _start_search(message: Message, bot: Bot, gender_filter=None):
    uid = message.from_user.id

    if await _check_banned(message):
        return
    if not await _check_registered(message):
        return

    # Gender search is premium
    if gender_filter:
        u = await db.get_user(uid)
        from config import PREMIUM_ENABLED
        if PREMIUM_ENABLED and not u.get("premium"):
            u_status = "\u274c Not active"
            await message.answer(
                texts.GENDER_SEARCH_PREMIUM.format(status=u_status),
                reply_markup=keyboards.premium_payment(),
            )
            return

    if await db.is_in_chat(uid):
        await message.answer(texts.ALREADY_IN_CHAT)
        return
    if await db.is_waiting(uid):
        await message.answer(texts.ALREADY_SEARCHING)
        return

    await db.add_waiting(uid, gender_filter)
    await message.answer(texts.SEARCHING)
    await asyncio.sleep(0.3)
    await _try_match(uid, bot)


@router.message(Command("search"))
@router.message(F.text == "\u00bb Next")
async def cmd_search(message: Message, bot: Bot):
    # "Next" when not in chat = new search
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

async def _end_chat(uid: int, bot: Bot, reason: str = "you"):
    partner_id = await db.remove_pair(uid)
    await db.remove_waiting(uid)
    _rated.discard((uid, partner_id))
    _rated.discard((partner_id, uid))

    if reason == "you":
        await bot.send_message(
            uid,
            texts.CHAT_ENDED_YOU,
            reply_markup=keyboards.post_chat(partner_id) if partner_id else keyboards.main_menu(),
        )
        if partner_id:
            await bot.send_message(
                partner_id,
                texts.CHAT_ENDED_PARTNER,
            )
    else:
        await bot.send_message(uid, texts.CHAT_ENDED_PARTNER)


@router.message(Command("stop"))
@router.message(F.text == "\U0001f534 Stop")
async def cmd_stop(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if not await db.is_in_chat(uid):
        await db.remove_waiting(uid)
        await message.answer(texts.NOT_IN_CHAT, reply_markup=keyboards.main_menu())
        return
    await _end_chat(uid, bot, reason="you")


# ── NEXT ──────────────────────────────────────────────────────────────────────

@router.message(Command("next"))
async def cmd_next(message: Message, bot: Bot):
    uid = message.from_user.id

    if await _check_banned(message):
        return
    if not await _check_registered(message):
        return

    if await db.is_in_chat(uid):
        partner_id = await db.remove_pair(uid)
        _rated.discard((uid, partner_id))
        _rated.discard((partner_id, uid))
        # Notify partner
        if partner_id:
            try:
                await bot.send_message(partner_id, texts.CHAT_ENDED_PARTNER)
            except Exception:
                pass

    await message.answer(texts.NEXT_SEARCHING)
    await db.add_waiting(uid)
    await asyncio.sleep(0.3)
    await _try_match(uid, bot)


# ── POST-CHAT INLINE BUTTONS ──────────────────────────────────────────────────

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

    # Remove just the like/dislike buttons but keep block/report
    try:
        b = keyboards.InlineKeyboardBuilder()  # type: ignore
        # Rebuild without Like/Dislike
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        nb = InlineKeyboardBuilder()
        nb.button(text="\U0001f6ab Block user",  callback_data=f"post:block:{partner_id}")
        nb.button(text="\U0001f6a9 Report user", callback_data=f"post:report:{partner_id}")
        nb.adjust(1)
        await call.message.edit_reply_markup(reply_markup=nb.as_markup())
    except Exception:
        pass


@router.callback_query(F.data.startswith("post:block:"))
async def cb_post_block(call: CallbackQuery):
    partner_id = int(call.data.split(":")[2])
    uid = call.from_user.id

    u = await db.get_user(uid)
    from config import PREMIUM_ENABLED
    if PREMIUM_ENABLED and (not u or not u.get("premium")):
        await call.answer(texts.BLOCK_PREMIUM_ONLY, show_alert=True)
        return

    result = await db.block_user(uid, partner_id)
    if result == "ok":
        await call.answer(texts.BLOCK_OK, show_alert=True)
    elif result == "already":
        await call.answer(texts.BLOCK_ALREADY, show_alert=True)
    elif result == "limit":
        await call.answer(texts.BLOCK_LIMIT, show_alert=True)
    else:
        await call.answer()

    # Remove block button after action
    try:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        nb = InlineKeyboardBuilder()
        nb.button(text="\U0001f6a9 Report user", callback_data=f"post:report:{partner_id}")
        nb.adjust(1)
        await call.message.edit_reply_markup(reply_markup=nb.as_markup())
    except Exception:
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
async def report_reason_received(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data.get("report_target")
    reason = (message.text or "").strip()[:300]
    if not reason:
        await message.answer("Please send a reason.")
        return

    await db.add_report(message.from_user.id, target, reason)
    await state.clear()
    await message.answer(texts.REPORT_OK)


# ── MESSAGE RELAY ─────────────────────────────────────────────────────────────

async def _get_partner_or_ignore(uid: int) -> int | None:
    return await db.get_partner(uid)


@router.message(F.text & ~F.text.startswith("/"))
async def relay_text(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid:
        return
    try:
        sent = await bot.send_message(pid, message.text)
        _last_msg[message.from_user.id] = {
            "own": message.message_id,
            "partner_msg": sent.message_id,
            "partner_id": pid,
        }
    except Exception as e:
        logger.warning("relay_text: %s", e)


@router.message(F.photo)
async def relay_photo(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_photo(pid, message.photo[-1].file_id, caption=message.caption or "")
    except Exception as e: logger.warning("relay_photo: %s", e)


@router.message(F.sticker)
async def relay_sticker(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_sticker(pid, message.sticker.file_id)
    except Exception as e: logger.warning("relay_sticker: %s", e)


@router.message(F.voice)
async def relay_voice(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_voice(pid, message.voice.file_id, caption=message.caption or "")
    except Exception as e: logger.warning("relay_voice: %s", e)


@router.message(F.video)
async def relay_video(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_video(pid, message.video.file_id, caption=message.caption or "")
    except Exception as e: logger.warning("relay_video: %s", e)


@router.message(F.video_note)
async def relay_video_note(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_video_note(pid, message.video_note.file_id)
    except Exception as e: logger.warning("relay_video_note: %s", e)


@router.message(F.document)
async def relay_document(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_document(pid, message.document.file_id, caption=message.caption or "")
    except Exception as e: logger.warning("relay_document: %s", e)


@router.message(F.audio)
async def relay_audio(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_audio(pid, message.audio.file_id, caption=message.caption or "")
    except Exception as e: logger.warning("relay_audio: %s", e)


@router.message(F.animation)
async def relay_animation(message: Message, bot: Bot):
    pid = await _get_partner_or_ignore(message.from_user.id)
    if not pid: return
    try: await bot.send_animation(pid, message.animation.file_id, caption=message.caption or "")
    except Exception as e: logger.warning("relay_animation: %s", e)
