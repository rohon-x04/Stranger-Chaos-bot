"""Global middleware: registers users and blocks banned ones everywhere."""

from html import escape

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

import database as db
import texts
from config import ADMIN_IDS


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None or user.is_bot:
            return await handler(event, data)

        u = await db.ensure_user(user.id, user.username or "", user.first_name or "")
        if u.get("banned") and user.id not in ADMIN_IDS:
            reason = escape(u.get("ban_reason") or "Unknown", quote=False)
            if isinstance(event, CallbackQuery):
                await event.answer("\U0001f6ab You are banned.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer(texts.BANNED.format(reason=reason))
            return None
        return await handler(event, data)
