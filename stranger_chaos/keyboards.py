"""All keyboards in one place."""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ── Main reply keyboard (matches screenshot exactly) ─────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\u00bb Next"), KeyboardButton(text="\U0001f534 Stop")],
            [KeyboardButton(text="\U0001f467 Find Girl"), KeyboardButton(text="\U0001f466 Find Boy")],
            [KeyboardButton(text="\U0001f464 Profile")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Type a message or pick an action\u2026",
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Registration keyboards ────────────────────────────────────────────────────

def gender_select() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\U0001f466 Male",   callback_data="reg_gender:male")
    b.button(text="\U0001f467 Female", callback_data="reg_gender:female")
    b.adjust(2)
    return b.as_markup()


# ── Profile edit buttons (matches screenshot) ─────────────────────────────────

def profile_edit() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\U0001f4c5 Age",     callback_data="edit:age")
    b.button(text="\u2753 Gender",      callback_data="edit:gender")
    b.button(text="\U0001f310 Country", callback_data="edit:country")
    b.button(text="\U0001f4a0 Premium", callback_data="edit:premium")
    b.adjust(2)
    return b.as_markup()


# ── Post-chat rating + action buttons (matches screenshot) ───────────────────

def post_chat(partner_id: int, show_block: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\U0001f44d Like",    callback_data=f"rate:like:{partner_id}")
    b.button(text="\U0001f44e Dislike", callback_data=f"rate:dislike:{partner_id}")
    if show_block:
        b.button(text="\U0001f6ab Block user",  callback_data=f"post:block:{partner_id}")
    b.button(text="\U0001f6a9 Report user", callback_data=f"post:report:{partner_id}")
    b.adjust(2, 1, 1)
    return b.as_markup()


# ── Admin report action buttons ───────────────────────────────────────────────

def admin_report_btns(report_idx: int, reported_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\u2705 Resolve",  callback_data=f"admin_resolve:{report_idx}")
    b.button(text="\U0001f6ab Ban",  callback_data=f"admin_ban:{reported_id}:{report_idx}")
    b.adjust(2)
    return b.as_markup()


# ── Premium payment choice (matches screenshot) ───────────────────────────────

def premium_payment() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="\U0001f1ee\U0001f1f3 Indian Users",   callback_data="pay:india")
    b.button(text="\U0001f310 Foreign Users", callback_data="pay:foreign")
    b.adjust(2)
    return b.as_markup()
