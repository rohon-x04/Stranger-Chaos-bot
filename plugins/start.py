"""
/start     — welcome + registration flow
/profile   — view & edit profile (age, gender, country, interests)
/interests — pick interests used for smarter matching        (NEW)
/daily     — claim a daily bonus of searches with a streak   (NEW)
"""

import logging
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

import config
import database as db
import texts
import keyboards
from states import Register, EditProfile
from config import BOT_NAME, MIN_AGE, MAX_AGE, FREE_DAILY_SEARCHES, PREMIUM_DAILY_SEARCHES

logger = logging.getLogger(__name__)
router = Router()


# ── Helpers ───────────────────────────────────────────────────────────────────

def gender_icon(g: str) -> str:
    return "\U0001f466" if g == "male" else "\U0001f467"


def interests_label(keys: list[str]) -> str:
    return ", ".join(config.INTERESTS.get(k, k) for k in keys) if keys else "not set"


async def send_profile(message: Message, uid: int):
    u = await db.get_user(uid)
    if not u or not u.get("registered"):
        await message.answer(texts.NOT_REGISTERED)
        return

    left = await db.searches_left(uid)
    daily = PREMIUM_DAILY_SEARCHES if u.get("premium") else FREE_DAILY_SEARCHES
    prem = u.get("premium", False)

    text = texts.PROFILE.format(
        age=u["age"],
        gender_icon=gender_icon(u["gender"]),
        gender=u["gender"].capitalize(),
        country=texts.html_escape(u["country"]),
        interests=interests_label(u.get("interests", [])),
        left=left,
        daily=daily,
        status_icon="✅" if prem else "❌",
        status="Premium active" if prem else "Not active",
    )
    await message.answer(text, reply_markup=keyboards.profile_edit())


async def _send_interests_picker(message: Message, uid: int):
    sel = await db.get_interests(uid)
    await message.answer(
        texts.INTERESTS_PICK.format(max=config.MAX_INTERESTS),
        reply_markup=keyboards.interests_picker(sel),
    )


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    u = await db.ensure_user(user.id, user.username or "", user.first_name or "")
    await state.clear()

    if u.get("registered"):
        await message.answer(
            texts.WELCOME_BACK.format(bot_name=BOT_NAME),
            reply_markup=keyboards.main_menu(),
        )
        return

    await message.answer(texts.WELCOME)
    await message.answer(texts.ASK_AGE.format(min=MIN_AGE, max=MAX_AGE))
    await state.set_state(Register.age)


# ── Registration: age ─────────────────────────────────────────────────────────

@router.message(Register.age)
async def reg_age(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or not (MIN_AGE <= int(text) <= MAX_AGE):
        await message.answer(texts.AGE_INVALID.format(min=MIN_AGE, max=MAX_AGE))
        return
    await state.update_data(age=int(text))
    await message.answer(texts.ASK_GENDER, reply_markup=keyboards.gender_select())
    await state.set_state(Register.gender)


# ── Registration: gender (inline button) ─────────────────────────────────────

@router.callback_query(Register.gender, F.data.startswith("reg_gender:"))
async def reg_gender(call: CallbackQuery, state: FSMContext):
    gender = call.data.split(":")[1]
    await state.update_data(gender=gender)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(texts.ASK_COUNTRY)
    await state.set_state(Register.country)
    await call.answer()


# ── Registration: country ─────────────────────────────────────────────────────

@router.message(Register.country)
async def reg_country(message: Message, state: FSMContext):
    country = (message.text or "").strip()[:60]
    if not country:
        await message.answer(texts.ASK_COUNTRY)
        return

    data = await state.get_data()
    if "age" not in data or "gender" not in data:   # state lost (e.g. restart)
        await state.clear()
        await message.answer(texts.NOT_REGISTERED)
        return

    await db.update_user(
        message.from_user.id,
        age=data["age"],
        gender=data["gender"],
        country=country,
        registered=True,
    )
    await state.clear()

    await message.answer(texts.REG_DONE, reply_markup=keyboards.main_menu())
    await _send_interests_picker(message, message.from_user.id)   # optional step


# ── /profile + Profile button ─────────────────────────────────────────────────

@router.message(Command("profile"))
@router.message(F.text == "\U0001f464 Profile")
async def cmd_profile(message: Message, state: FSMContext):
    await state.clear()
    await send_profile(message, message.from_user.id)


# ── Profile edit callbacks ────────────────────────────────────────────────────

@router.callback_query(F.data == "edit:age")
async def edit_age_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer(texts.ASK_AGE.format(min=MIN_AGE, max=MAX_AGE))
    await state.set_state(EditProfile.age)
    await call.answer()


@router.message(EditProfile.age)
async def edit_age_save(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or not (MIN_AGE <= int(text) <= MAX_AGE):
        await message.answer(texts.AGE_INVALID.format(min=MIN_AGE, max=MAX_AGE))
        return
    await db.update_user(message.from_user.id, age=int(text))
    await state.clear()
    await message.answer("✅ Age updated!")
    await send_profile(message, message.from_user.id)


@router.callback_query(F.data == "edit:gender")
async def edit_gender_start(call: CallbackQuery, state: FSMContext):
    # Own state: the old code reused the registration state, which then asked
    # for a country and crashed on a missing "age" key.
    await call.message.answer(texts.ASK_GENDER, reply_markup=keyboards.gender_select())
    await state.set_state(EditProfile.gender)
    await call.answer()


@router.callback_query(EditProfile.gender, F.data.startswith("reg_gender:"))
async def edit_gender_save(call: CallbackQuery, state: FSMContext):
    gender = call.data.split(":")[1]
    if gender not in ("male", "female"):
        await call.answer()
        return
    await db.update_user(call.from_user.id, gender=gender)
    await state.clear()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await call.message.answer("✅ Gender updated!")
    await send_profile(call.message, call.from_user.id)
    await call.answer()


@router.callback_query(F.data == "edit:country")
async def edit_country_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer(texts.ASK_COUNTRY)
    await state.set_state(EditProfile.country)
    await call.answer()


@router.message(EditProfile.country)
async def edit_country_save(message: Message, state: FSMContext):
    country = (message.text or "").strip()[:60]
    if not country:
        await message.answer(texts.ASK_COUNTRY)
        return
    await db.update_user(message.from_user.id, country=country)
    await state.clear()
    await message.answer("✅ Country updated!")
    await send_profile(message, message.from_user.id)


@router.callback_query(F.data == "edit:premium")
async def edit_premium_info(call: CallbackQuery):
    u = await db.get_user(call.from_user.id)
    prem = u.get("premium", False) if u else False
    status = "✅ Active" if prem else "❌ Not active"
    await call.message.answer(
        texts.PREMIUM_INFO.format(status=status),
        reply_markup=keyboards.premium_payment(),
    )
    await call.answer()


# ── Interests (NEW) ───────────────────────────────────────────────────────────

@router.message(Command("interests"))
@router.message(F.text == "\U0001f3af Interests")
async def cmd_interests(message: Message, state: FSMContext):
    await state.clear()
    u = await db.get_user(message.from_user.id)
    if not u or not u.get("registered"):
        await message.answer(texts.NOT_REGISTERED)
        return
    await _send_interests_picker(message, message.from_user.id)


@router.callback_query(F.data == "edit:interests")
async def edit_interests_start(call: CallbackQuery):
    await _send_interests_picker(call.message, call.from_user.id)
    await call.answer()


async def _refresh_picker(call: CallbackQuery):
    sel = await db.get_interests(call.from_user.id)
    try:
        await call.message.edit_reply_markup(reply_markup=keyboards.interests_picker(sel))
    except TelegramBadRequest:
        pass  # "message is not modified"


@router.callback_query(F.data.startswith("int:t:"))
async def cb_interest_toggle(call: CallbackQuery):
    key = call.data.split(":", 2)[2]
    result = await db.toggle_interest(call.from_user.id, key)
    if result == "limit":
        await call.answer(texts.INTERESTS_LIMIT.format(max=config.MAX_INTERESTS), show_alert=True)
        return
    await _refresh_picker(call)
    await call.answer()


@router.callback_query(F.data == "int:clear")
async def cb_interest_clear(call: CallbackQuery):
    await db.clear_interests(call.from_user.id)
    await _refresh_picker(call)
    await call.answer(texts.INTERESTS_CLEARED)


@router.callback_query(F.data == "int:done")
async def cb_interest_done(call: CallbackQuery):
    sel = await db.get_interests(call.from_user.id)
    try:
        await call.message.edit_text(
            f"{texts.INTERESTS_SAVED}\n\n\U0001f3af <b>{interests_label(sel)}</b>",
            reply_markup=None,
        )
    except TelegramBadRequest:
        pass
    await call.answer()


# ── Daily bonus (NEW) ─────────────────────────────────────────────────────────

@router.message(Command("daily"))
async def cmd_daily(message: Message):
    u = await db.get_user(message.from_user.id)
    if not u or not u.get("registered"):
        await message.answer(texts.NOT_REGISTERED)
        return
    r = await db.claim_daily(message.from_user.id)
    if r["ok"]:
        await message.answer(texts.DAILY_OK.format(amount=r["amount"], streak=r["streak"]))
    else:
        await message.answer(texts.DAILY_ALREADY.format(streak=r["streak"]))


# ── Premium payment stubs ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay:"))
async def pay_handler(call: CallbackQuery):
    region = call.data.split(":")[1]
    region_text = "India" if region == "india" else "International"
    await call.message.answer(
        f"\U0001f4b3 <b>{region_text} Payment</b>\n\n"
        f"Contact our support to get Premium:\n{texts.SUPPORT_LINK}\n\n"
        "Tell them your Telegram ID:\n"
        f"<code>{call.from_user.id}</code>"
    )
    await call.answer()
