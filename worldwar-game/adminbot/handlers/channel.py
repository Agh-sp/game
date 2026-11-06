"""دستورهای تست کانال و گپ رسمی بازی.

    /testchannel  → بررسی ادمین بودن ربات در کانال @Jangjhani313 و ارسال یک خبر تستی
    /channels     → نمایش کانال خبری، کانال‌های عضویت اجباری و گروه رسمی
    /setchannels  → تنظیم سریع کانال/گروه رسمی بازی
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core import config as cfg
from core.db import db, get_setting, set_setting
from core.economy import announce, check_channel

router = Router()


async def _channels_text() -> str:
    join_raw = await get_setting("join_channels", "[]")
    channel = await get_setting("announcement_channel", "")
    group = await get_setting("game_group", "")
    return (
        f"📡 <b>تنظیمات کانال و گپ «{cfg.GAME_NAME}»</b>\n\n"
        f"📢 کانال خبری: <code>{channel or '—'}</code>\n"
        f"👥 گروه/گپ رسمی: <code>{group or '—'}</code>\n"
        f"🔐 کانال‌های عضویت اجباری: <code>{join_raw or '[]'}</code>\n\n"
        "برای تست ارسال خبر به کانال: /testchannel\n"
        "برای تنظیم مجدد پیش‌فرض‌ها: /setchannels"
    )


@router.message(Command("channels"))
async def cmd_channels(message: Message, state: FSMContext, admin: dict, perms: set):
    await message.answer(await _channels_text())


@router.message(Command("setchannels"))
async def cmd_set_channels(message: Message, state: FSMContext, admin: dict, perms: set):
    await set_setting("announcement_channel", cfg.OFFICIAL_CHANNEL)
    await set_setting("game_group", cfg.OFFICIAL_GROUP)
    await set_setting("join_channels", __import__("json").dumps(list(cfg.OFFICIAL_CHANNELS),
                                                              ensure_ascii=False))
    await message.answer(
        "✅ کانال و گپ رسمی تنظیم شد:\n\n"
        f"📢 کانال خبری: <b>{cfg.OFFICIAL_CHANNEL}</b>\n"
        f"👥 گپ بازی: <b>{cfg.OFFICIAL_GROUP}</b>\n\n"
        "⚠️ یادت نرود ربات <b>بازی</b> را در کانال خبری ادمین کنی، وگرنه خبری ارسال نمی‌شود."
    )


@router.message(Command("testchannel"))
async def cmd_test_channel(message: Message, state: FSMContext, admin: dict, perms: set):
    """بررسی سلامت کانال خبری + ارسال یک خبر تستی."""
    status = await check_channel(message.bot)
    if not status.get("ok"):
        await message.answer(
            "❌ <b>کانال خبری آماده نیست</b>\n\n"
            f"📢 کانال: <code>{status.get('channel') or '—'}</code>\n"
            f"🧾 خطا: <code>{status.get('error') or 'نامشخص'}</code>\n\n"
            "🛠 راه‌حل:\n"
            "۱) ربات <b>بازی</b> (@WorldWarWordbot) را در کانال ادمین کن (اجازهٔ ارسال پیام)\n"
            "۲) مقدار <code>announcement_channel</code> را در ⚙️ تنظیمات درست کن\n"
            "۳) دوباره /testchannel بزن"
        )
        return

    await announce(
        message.bot,
        "🧪 <b>خبر تستی</b>\n\n"
        "این پیام آزمایشی است؛ از این پس اخبار جنگ، پیروزی، بیانیه، رأی‌گیری و "
        "وضعیت روزانه جهان همین‌جا منتشر می‌شود.",
        section="general",
    )
    await message.answer(
        "✅ خبر تستی با موفقیت به کانال ارسال شد.\n\n"
        f"📢 کانال: <b>{status.get('channel')}</b>\n"
        f"🎮 فرستنده: @{status.get('bot') or 'ربات بازی'}"
    )


@router.callback_query(F.data == "a|testchannel")
async def cb_test_channel(call: CallbackQuery, state: FSMContext, admin: dict, perms: set):
    await call.answer("در حال بررسی کانال...")
    status = await check_channel(call.bot)
    if not status.get("ok"):
        await call.message.answer(
            f"❌ کانال آماده نیست: <code>{status.get('error')}</code>")
        return
    await announce(call.bot, "🧪 <b>خبر تستی از پنل مدیریت</b>", section="general")
    await call.message.answer("✅ خبر تستی به کانال ارسال شد.")


async def channel_hint() -> str:
    """متن کوتاه وضعیت کانال برای نمایش در پنل ادمین."""
    channel = await get_setting("announcement_channel", "")
    row = 0
    try:
        from core.db import db as _db
        r = await _db.fetchone("SELECT COUNT(*) c FROM wars WHERE status='active'")
        row = int((r or {}).get("c") or 0)
    except Exception:
        pass
    return f"📢 کانال خبری: {channel or '—'} | 🧪 /testchannel"
