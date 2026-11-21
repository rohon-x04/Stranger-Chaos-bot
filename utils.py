"""Small shared helpers."""

import html
import logging
from collections import OrderedDict
from typing import Optional

from aiogram import Bot

import config
import keyboards

logger = logging.getLogger(__name__)


def esc(s) -> str:
    """HTML-escape any user supplied text before putting it in a message."""
    return html.escape(str(s), quote=False)


class MessageMap:
    """
    Remembers which relayed message is which, so that
      * replies keep their reply-thread on the partner's side
      * /del can remove a message on both sides

    Bounded (LRU) so memory can't grow forever.
    """

    def __init__(self, limit: int = 20000):
        self._limit = limit
        # (sender_id, sender_msg_id) -> (receiver_id, receiver_msg_id)
        self._sent: OrderedDict = OrderedDict()
        # (receiver_id, receiver_msg_id) -> (sender_id, sender_msg_id)
        self._recv: OrderedDict = OrderedDict()

    def _put(self, d: OrderedDict, k, v):
        d[k] = v
        d.move_to_end(k)
        while len(d) > self._limit:
            d.popitem(last=False)

    def record(self, sender: int, sender_mid: int, receiver: int, receiver_mid: int):
        self._put(self._sent, (sender, sender_mid), (receiver, receiver_mid))
        self._put(self._recv, (receiver, receiver_mid), (sender, sender_mid))

    def own_message(self, uid: int, mid: int) -> Optional[tuple[int, int]]:
        """If `uid` sent message `mid`, return (partner_id, partner_msg_id)."""
        return self._sent.get((uid, mid))

    def reply_target(self, uid: int, replied_mid: int) -> Optional[tuple[int, int]]:
        """
        `uid` replied to `replied_mid`. Return (partner_id, message id in the
        partner's chat to reply to).
        """
        own = self._sent.get((uid, replied_mid))
        if own:
            return own                       # replying to own message
        other = self._recv.get((uid, replied_mid))
        if other:
            return other                     # replying to partner's message
        return None

    def forget(self, uid: int, mid: int):
        v = self._sent.pop((uid, mid), None)
        if v:
            self._recv.pop(v, None)


msg_map = MessageMap()


async def notify_admins_of_report(bot: Bot, report: dict):
    """DM every admin about a new report, with Resolve / Ban buttons."""
    if not config.NOTIFY_ADMINS_ON_REPORT:
        return
    text = (
        f"\U0001f6a8 <b>New report #{report['id']}</b>\n"
        f"Reporter: <code>{report['reporter']}</code>\n"
        f"Reported: <code>{report['reported']}</code>\n"
        f"Reason: <i>{esc(report['reason'])}</i>"
    )
    kb = keyboards.admin_report_btns(report["id"], report["reported"])
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception as e:  # admin may not have started the bot
            logger.debug("notify admin %s failed: %s", admin_id, e)
