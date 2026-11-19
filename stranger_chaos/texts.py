"""All bot message text — edit freely."""

from config import BOT_NAME, SUPPORT_LINK, MAX_BLOCK_LIST, MIN_AGE, MAX_AGE, FREE_DAILY_SEARCHES, PREMIUM_DAILY_SEARCHES

# ── Welcome ───────────────────────────────────────────────────────────────────
WELCOME = (
    "\U0001f49c\U0001f499 <b>Welcome to Anonymous Chat!</b>\n\n"
    "Talk to random people anonymously. No names, no pressure.\n"
    "First, let's quickly set up your profile."
)

WELCOME_BACK = (
    "\U0001f499 <b>Welcome back to {bot_name}!</b>\n\n"
    "Use the buttons below to find a stranger."
)

# ── Registration ──────────────────────────────────────────────────────────────
ASK_AGE      = "\U0001f4c5 Send your <b>age</b> ({min}-{max}):"
AGE_INVALID  = "\u2705 Please send a valid age ({min}-{max})."
ASK_GENDER   = "\u2753 Select your <b>gender</b>:"
ASK_COUNTRY  = "\U0001f310 Send your <b>country</b> (e.g. India):"
REG_DONE     = "\u2705 <b>Registration complete!</b>"

# ── Profile ───────────────────────────────────────────────────────────────────
PROFILE = (
    "<b>Your profile</b>\n\n"
    "Age: <b>{age}</b>\n"
    "Gender: {gender_icon} <b>{gender}</b>\n"
    "Country: <b>{country}</b>\n"
    "Searches left today: <b>{left}/{daily}</b>\n"
    "Status: {status_icon} <b>{status}</b>"
)

# ── Search ────────────────────────────────────────────────────────────────────
SEARCHING = (
    "\U0001f300 Looking for a partner\u2026\n\n"
    "/stop \u2014 stop searching"
)
PARTNER_FOUND = (
    "\U0001f499 <b>Partner found</b> |  {badge}\n\n"
    "/next \u2014 skip to a new partner\n"
    "/stop \u2014 end the dialogue\n"
    "/link \u2014 share your telegram profile"
)
ALREADY_SEARCHING = "\u23f3 Already searching\u2026 please wait."
ALREADY_IN_CHAT   = "\u26a0\ufe0f You're already chatting! Use /next or /stop."
NOT_IN_CHAT       = "\u274c You're not in a chat. Use Search to find someone!"
NO_SEARCHES_LEFT  = (
    "\u274c <b>No searches left today!</b>\n\n"
    "Get more by:\n"
    "  \u2022 Having partners <b>Like \U0001f44d</b> you\n"
    "  \u2022 Upgrading to <b>Premium</b>\n\n"
    f"Support: {SUPPORT_LINK}"
)
NOT_REGISTERED = (
    "\u26a0\ufe0f Please complete your profile first!\n"
    "Send /start to register."
)

# ── Chat end ──────────────────────────────────────────────────────────────────
CHAT_ENDED_YOU = (
    "\u2705 You stopped the chat.\n\n"
    "<b>How was your chat?</b>\n\n"
    "\U0001f44d Like \u2192 partner gets +1 search\n"
    "\U0001f44e Dislike \u2192 partner gets -1 search"
)
CHAT_ENDED_PARTNER = (
    "\U0001f44b\u200d Your partner has stopped the chat.\n\n"
    "/next \u2014 find a new partner"
)
NEXT_SEARCHING = "\u23ed Searching for a new partner\u2026"

# ── Rating ────────────────────────────────────────────────────────────────────
RATED_LIKE    = "\U0001f44d Liked! Your partner gets +1 search."
RATED_DISLIKE = "\U0001f44e Disliked. Partner gets -1 search."
ALREADY_RATED = "\u26a0\ufe0f You already rated this conversation."

# ── Link ──────────────────────────────────────────────────────────────────────
LINK_NO_USERNAME = (
    "\u274c <b>No username set.</b>\n\n"
    "Go to: Settings \u2192 My Profile \u2192 Username\n"
    "Set a username, then try /link again."
)
LINK_OK = "\U0001f517 <b>Your profile link:</b>\n<code>https://t.me/{username}</code>"

# ── Block ─────────────────────────────────────────────────────────────────────
BLOCK_NOT_IN_CHAT  = "\u274c You need to be in a chat to block your partner."
BLOCK_OK           = "\U0001f6ab User blocked! You'll never be matched with them again."
BLOCK_ALREADY      = "\u26a0\ufe0f You've already blocked this user."
BLOCK_LIMIT        = f"\u26a0\ufe0f Block limit reached ({MAX_BLOCK_LIST} max). Remove someone from /blocklist first."
BLOCK_PREMIUM_ONLY = "\U0001f512 /block is a <b>Premium</b> feature.\n\n" + SUPPORT_LINK

BLOCKLIST_EMPTY  = "\U0001f4d2 Your block list is empty."
BLOCKLIST_HEADER = "\U0001f4d2 <b>Block List</b>\n\n"
BLOCKLIST_ROW    = "  <b>{n}.</b> User <code>{uid}</code>"

UNBLOCK_USAGE     = "Usage: <code>/unblock &lt;id&gt;</code>  (see /blocklist for IDs)"
UNBLOCK_OK        = "\U0001f513 User unblocked!"
UNBLOCK_NOT_FOUND = "\u274c No entry with that ID in your block list."

# ── Del ───────────────────────────────────────────────────────────────────────
DEL_PREMIUM_ONLY  = "\U0001f512 /del is a <b>Premium</b> feature.\n\n" + SUPPORT_LINK
DEL_NOT_IN_CHAT   = "\u274c You must be in a chat to use /del."
DEL_REPLY_NEEDED  = "\u21a9\ufe0f Reply to <b>your own message</b> with /del."
DEL_NOT_YOUR_MSG  = "\u26a0\ufe0f You can only delete your own messages."
DEL_OK            = "\U0001f5d1 Message deleted for both sides."

# ── Report ────────────────────────────────────────────────────────────────────
REPORT_NOT_IN_CHAT = "\u274c You need to be in a chat to report someone."
REPORT_USAGE       = "Usage: <code>/report &lt;reason&gt;</code>"
REPORT_OK          = (
    "\U0001f6a8 <b>Report submitted!</b>\n\n"
    "Our admins will review the conversation. "
    "Fake reports will result in action against your account."
)

# ── Premium ───────────────────────────────────────────────────────────────────
PREMIUM_INFO = (
    "\U0001f4a0 <b>Premium Benefits</b>\n\n"
    "\u2022 \U0001f467 Find Girl / \U0001f466 Find Boy: search by gender\n"
    f"\u2022 \U0001f50d <b>{PREMIUM_DAILY_SEARCHES}</b> daily searches (free: {FREE_DAILY_SEARCHES})\n"
    "\u2022 \U0001f6ab /block, /unblock: block up to 30 users\n"
    "\u2022 \U0001f5d1 /del: delete your sent messages\n"
    "\u2022 \U0001f4a0 Premium badge shown to your partners\n\n"
    "Status: {status}\n\n"
    "Contact support to upgrade:\n" + SUPPORT_LINK
)
PREMIUM_GRANTED = "\U0001f4a0 <b>You now have Premium!</b>\n\nEnjoy all benefits!"
GENDER_SEARCH_PREMIUM = (
    "\U0001f4a0 Gender-wise search is a Premium feature.\n\n"
    + PREMIUM_INFO
)

# ── Admin ─────────────────────────────────────────────────────────────────────
ADMIN_STATS = (
    "\U0001f4ca <b>Bot Statistics</b>\n"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
    "\U0001f465 Total users:    <b>{total_users}</b>\n"
    "\u2705 Registered:     <b>{registered}</b>\n"
    "\U0001f4ac Active chats:   <b>{active_chats}</b>\n"
    "\u23f3 Waiting:        <b>{waiting}</b>\n"
    "\U0001f4a0 Premium:        <b>{premium}</b>\n"
    "\U0001f6a8 Open reports:   <b>{open_reports}</b> / {total_reports}\n"
    "\U0001f6ab Banned:         <b>{banned}</b>"
)
ADMIN_NOT_ADMIN       = "\U0001f6ab Not authorised."
ADMIN_BROADCAST_DONE  = "\U0001f4e3 Sent to <b>{n}</b> users ({failed} failed)."

# ── Banned ────────────────────────────────────────────────────────────────────
BANNED = (
    "\U0001f6ab <b>You have been banned.</b>\n\n"
    "Reason: <i>{reason}</i>\n\n"
    f"Appeal: {SUPPORT_LINK}"
)
