"""🔒 میدل‌ور یکپارچگی آپدیت‌ها (ربات بازی).

هر آپدیت تلگرام باید «ممکن» باشد. اگر کسی با توکن ربات یا از راه وبهوک، آپدیتی
بسازد که تلگرام هرگز نمی‌سازد، این لایه آن را قبل از رسیدن به هندلرها رد می‌کند:

  • پیام/کال‌بک از طرف یک **ربات** (is_bot) — تلگرام چنین چیزی به ربات نمی‌دهد؛
  • آپدیت بدون «فرستنده» (نه پیام، نه کال‌بک، نه عضویت و …)؛
  • پیام‌های خیلی قدیمی یا با تاریخ آینده (بیش از ۱۰ دقیقه اختلاف)؛
  • آپدیت‌هایی که `message.from.id` با `chat.id` گفتگوی خصوصی نمی‌خواند
    (جعل پیام خصوصی از طرف کاربر دیگر).

هر رد شدن در `security_events` ثبت می‌شود تا در پنل «🔐 امنیت» دیده شود.
"""
from __future__ import annotations

import logging
import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update

log = logging.getLogger("gamebot.integrity")

MAX_CLOCK_SKEW = 600  # ثانیه


def _stamp(value) -> int:
    """تبدیل date پیام (datetime در aiogram 3 یا عدد یونیکس) به ثانیه."""
    import datetime as _dt
    if isinstance(value, _dt.datetime):
        return int(value.timestamp())
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _user_of(event) -> object | None:
    for attr in ("from_user",):
        user = getattr(event, attr, None)
        if user is not None:
            return user
    for attr in ("message", "edited_message", "callback_query", "channel_post"):
        inner = getattr(event, attr, None)
        if inner is not None:
            user = getattr(inner, "from_user", None)
            if user is not None:
                return user
    return None


class IntegrityMiddleware(BaseMiddleware):
    """رد آپدیت‌های غیرممکن (ضد آپدیت جعلی/بازپخش)."""

    async def __call__(self, handler, event, data):
        from core import security as sec

        update = event if isinstance(event, Update) else None
        if update is not None and not any((
                update.message, update.edited_message, update.callback_query,
                update.inline_query, update.channel_post, update.edited_channel_post,
                update.my_chat_member, update.chat_member, update.chat_join_request,
                update.pre_checkout_query, update.poll_answer,
                update.business_connection, update.business_message)):
            return None

        user = data.get("event_from_user") or _user_of(event)
        if user is not None and getattr(user, "is_bot", False):
            await sec.record("auth_fail", getattr(user, "id", 0), "آپدیت از طرف ربات رد شد")
            log.warning("⛔️ آپدیت از طرف ربات رد شد: %s", getattr(user, "id", "?"))
            return None

        msg = event if isinstance(event, Message) else getattr(event, "message", None)
        if msg is None and isinstance(event, CallbackQuery):
            msg = event.message
        if msg is not None:
            now_ts = int(time.time())
            stamp = _stamp(getattr(msg, "date", 0))
            if stamp and abs(now_ts - stamp) > MAX_CLOCK_SKEW:
                await sec.record("auth_fail", getattr(getattr(msg, "from_user", None), "id", 0),
                                 f"پیام با تاریخ نامعتبر ({stamp})")
                log.warning("⛔️ پیام با تاریخ نامعتبر رد شد: %s", stamp)
                return None
            chat = getattr(msg, "chat", None)
            sender = getattr(msg, "from_user", None)
            if (chat is not None and sender is not None
                    and getattr(chat, "type", "") == "private"
                    and int(chat.id) != int(sender.id)):
                await sec.record("auth_fail", int(sender.id),
                                 f"جعل گفتگوی خصوصی: chat={chat.id} from={sender.id}")
                log.warning("⛔️ ناسازگاری chat/from رد شد")
                return None
        return await handler(event, data)
