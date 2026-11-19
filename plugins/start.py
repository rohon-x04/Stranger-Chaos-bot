"""
/start  — welcome + registration flow
/profile — view & edit profile
Profile button — same as /profile
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

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
        country=u["country"],
        left=left,
        daily=daily,
        status_icon="\u274c" if not prem else "\u2705",
        status="Not active" if not prem else "Premium active",
    )
    await message.answer(text, reply_markup=keyboards.profile_edit())


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    u = await db.ensure_user(user.id, user.username or "", user.first_name or "")

    if await db.is_banned(user.id):
        u = await db.get_user(user.id)
        await message.answer(texts.BANNED.format(reason=u.get("ban_reason", "Unknown")))
        return

    await state.clear()

    if u.get("registered"):
        await message.answer(
            texts.WELCOME_BACK.format(bot_name=BOT_NAME),
            reply_markup=keyboards.main_menu(),
        )
        return

    # Start registration
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
    country = (message.text or "").strip()
    if not country:
        await message.answer(texts.ASK_COUNTRY)
        return

    data = await state.get_data()
    uid = message.from_user.id

    await db.update_user(uid,
        age=data["age"],
        gender=data["gender"],
        country=country,
        registered=True,
    )
    await state.clear()

    await message.answer(texts.REG_DONE, reply_markup=keyboards.main_menu())


# ── /profile + Profile button ─────────────────────────────────────────────────

@router.message(Command("profile"))
@router.message(F.text == "\U0001f464 Profile")
async def cmd_profile(message: Message, state: FSMContext):
    await state.clear()
    await send_profile(message, message.from_user.id)


# ── Profile edit callbacks ─────────────────────────────────────────────────────

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
    await message.answer("\u2705 Age updated!")
    await send_profile(message, message.from_user.id)


@router.callback_query(F.data == "edit:gender")
async def edit_gender_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer(texts.ASK_GENDER, reply_markup=keyboards.gender_select())
    await state.set_state(Register.gender)
    await call.answer()


@router.callback_query(F.data == "edit:country")
async def edit_country_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer(texts.ASK_COUNTRY)
    await state.set_state(EditProfile.country)
    await call.answer()


@router.message(EditProfile.country)
async def edit_country_save(message: Message, state: FSMContext):
    country = (message.text or "").strip()
    if not country:
        await message.answer(texts.ASK_COUNTRY)
        return
    await db.update_user(message.from_user.id, country=country)
    await state.clear()
    await message.answer("\u2705 Country updated!")
    await send_profile(message, message.from_user.id)


@router.callback_query(F.data == "edit:premium")
async def edit_premium_info(call: CallbackQuery):
    u = await db.get_user(call.from_user.id)
    prem = u.get("premium", False) if u else False
    status = "\u2705 Active" if prem else "\u274c Not active"
    await call.message.answer(
        texts.PREMIUM_INFO.format(status=status),
        reply_markup=keyboards.premium_payment(),
    )
    await call.answer()


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
