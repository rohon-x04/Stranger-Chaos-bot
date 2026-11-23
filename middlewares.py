"""Global middleware: registers users and blocks banned or unsafe messages everywhere."""

import re
from html import escape

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

import database as db
import texts
from config import ADMIN_IDS


_URL_OR_DOMAIN_RE = re.compile(
    r"(?i)(?:https?://|t\.me/|telegram\.me/|te\.legra\.ph/|www\.)"
    r"|(?:\b[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+(?:[/?#]\S*)?\b)"
)
_MENTION_RE = re.compile(r"(?<!\w)@[a-zA-Z0-9_]{4,32}\b")


def contains_link_or_mention(message: Message) -> bool:
    """Return True if a Telegram entity or plain text contains a link or mention."""
    text = message.text or message.caption or ""
    entities = list(message.entities or []) + list(message.caption_entities or [])

    for entity in entities:
        entity_type = getattr(entity.type, "value", entity.type)
        if str(entity_type) in {"url", "text_link", "mention", "text_mention"}:
            return True

    if _MENTION_RE.search(text):
        return True
    return bool(_URL_OR_DOMAIN_RE.search(text))


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None or user.is_bot:
            return await handler(event, data)

        u = await db.ensure_user(user.id, user.username or "", user.first_name or "")
        if u.get("banned") and user.id not in ADMIN_IDS:
            reason = escape(u.get("ban_reason") or "Unknown", quote=False)
            if isinstance(event, CallbackQuery):
                await event.answer("🚫 You are banned.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer(texts.BANNED.format(reason=reason))
            return None

        if isinstance(event, Message) and contains_link_or_mention(event):
            await event.answer("🚫 Links are not allowed in chat. Your message was not sent.")
            return None

        return await handler(event, data)
