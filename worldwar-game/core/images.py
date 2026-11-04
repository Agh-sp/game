"""کتابخانه تصاویر دائمی + اعلان کانال همراه عکس.

ادمین در ربات ادمین برای هر بخش عکس با «اسم» ذخیره می‌کند (جدول images).
هر جا بازی بخواهد در کانال چیزی اعلام کند، با send_with_image عکس همان بخش
(یا اسم خاص) همراه پیام ارسال می‌شود؛ اگر عکسی نبود، فقط متن ارسال می‌شود.
"""
from core.db import db, get_setting
from core.utils import jloads

# بخش‌های قابل انتخاب برای عکس‌ها
IMAGE_SECTIONS = {
    "negotiation": "🕊 مذاکره دو کشور",
    "negotiation3": "🕊 مذاکره سه کشور",
    "treaty_military": "🤝 پیمان نظامی",
    "treaty_trade": "💼 رفیقای تجاری",
    "treaty_peace": "🕊 پیمان صلح",
    "treaty_trust": "🤫 پیمان اعتماد",
    "treaty_brothers": "👥 برادران تنی",
    "betray": "💥 خیانت به قرارداد",
    "direct_trade": "🔁 تجارت مستقیم (اختیاری)",
    "rescue": "🏥 سازمان نجات و حمایت",
    "strait": "⚓ تنگه‌ها",
    "currency": "💵 ارز اصلی",
    "season": "🎬 سیزن جدید",
    "flag": "🏳 پرچم کشورها",
    # بخش‌های رویدادهای بازی (اعلان جنگ، حمله، سازمان ملل، سایبری، پروژه‌ها)
    "war_declare": "⚔️ اعلان جنگ",
    "war_attack": "💥 حمله و گزارش نبرد",
    "un": "🗳 سازمان ملل و رای‌گیری",
    "cyber": "🕶 عملیات سایبری",
    "project": "🏗 پروژه و ساختمان",
    "government": "🏛 حکومت و دین",
    "base": "🏕 پایگاه نظامی",
    "tax": "💰 مالیات و درآمد",
    "daily": "📊 گزارش روزانه",
    "statement": "📢 بیانیه رسمی کشور",
    "politics": "🏛 سیاست، رهبری و انتخابات",
    "revolution": "🔥 انقلاب و ناآرامی",
    "oil": "🛢 نفت و تجارت خودکار",
    "general": "📦 عمومی (پشتیبان همه پیام‌ها)",
}


async def get_image(section: str = "", name: str = "") -> dict | None:
    """یافتن عکس: اول با اسم، بعد اولین عکسِ بخش."""
    if name:
        row = await db.fetchone("SELECT * FROM images WHERE name=?", (name,))
        if row and row["file_id"]:
            return row
    if section:
        row = await db.fetchone(
            "SELECT * FROM images WHERE section=? AND file_id!='' ORDER BY id DESC", (section,))
        if row:
            return row
    return None


_BOT_USERNAME_CACHE = ""


async def get_channel_bot_username(bot=None) -> str:
    """دریافت نام‌کاربری ربات بازی برای ساخت لینک ورود در کانال."""
    global _BOT_USERNAME_CACHE
    if _BOT_USERNAME_CACHE:
        return _BOT_USERNAME_CACHE
    if bot:
        try:
            me = await bot.get_me()
            if me and me.username:
                _BOT_USERNAME_CACHE = me.username
                return me.username
        except Exception:
            pass
    try:
        val = await get_setting("game_bot_username", "")
        if val:
            _BOT_USERNAME_CACHE = val.replace("@", "").strip()
            return _BOT_USERNAME_CACHE
    except Exception:
        pass
    return "FIRE_OF_War_Bot"


def channel_entry_markup(bot_username: str):
    """ساخت دکمه اینلاین ورود به ربات برای پیام‌های کانال."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 ورود به ربات", url=f"https://t.me/{bot_username}")]
    ])


async def send_with_image(bot, chat_id: str | int, text: str,
                          section: str = "", name: str = "",
                          reply_markup=None) -> object | None:
    """ارسال پیام به چت/کانال — اگر عکس موجود بود با عکس (کپشن)، وگرنه متن؛ همراه با دکمه ورود به ربات.

    ترتیب انتخاب عکس: اسم دقیق → عکس همان بخش → عکس «عمومی» (پشتیبان).
    اگر متن از ۱۰۲۴ کاراکتر (سقف کپشن تلگرام) بیشتر بود، عکس جدا و متن جدا ارسال می‌شود
    تا هیچ‌وقت بخشی از پیام حذف نشود.
    """
    username = await get_channel_bot_username(bot)
    footer = f"\n\n🎮 <b>ورود به ربات:</b> @{username}"
    full_text = text if f"@{username}" in text else (text + footer)
    rm = reply_markup or channel_entry_markup(username)

    img = await get_image(section, name)
    if not img and section:
        img = await get_image("general")
    file_id = (img or {}).get("file_id") if img else ""
    try:
        if file_id and len(full_text) <= 1024:
            return await bot.send_photo(chat_id, file_id, caption=full_text, reply_markup=rm)
        elif file_id:
            # متن بلندتر از سقف کپشن: ابتدا عکس، سپس کل متن
            try:
                await bot.send_photo(chat_id, file_id, caption=text[:900] + "…")
            except Exception:
                pass
            return await bot.send_message(chat_id, full_text, reply_markup=rm)
        else:
            return await bot.send_message(chat_id, full_text, reply_markup=rm)
    except Exception:
        try:
            return await bot.send_message(chat_id, full_text, reply_markup=rm)
        except Exception:
            try:
                return await bot.send_message(chat_id, full_text)
            except Exception:
                return None


async def announce_img(bot, text: str, section: str = "", name: str = "", reply_markup=None) -> None:
    """اعلان کانال همراه عکس کتابخانه (در صورت وجود) و دکمه ورود به ربات."""
    channel = await get_setting("announcement_channel", "")
    if not channel:
        return
    await send_with_image(bot, channel, text, section, name, reply_markup=reply_markup)


async def get_country_flag_photo(country: dict) -> str | None:
    """دریافت بهترین تصویر پرچم: ۱) انتخابی کاربر/ادمین (flag_url) ۲) کتابخانه عکس‌ها ۳) لینک FlagCDN."""
    if not country:
        return None
    # اگر کاربر یا ادمین عکسی را از گالری برای کشور انتخاب کرده باشد
    if country.get("flag_url"):
        return country["flag_url"]
    # جستجو در کتابخانه تصاویر با اسم کشور یا بخش پرچم
    c_name = country.get("name", "")
    img = (await get_image(name=f"پرچم {c_name}") or
           await get_image(name=c_name) or
           await get_image("flag", f"flag_{country.get('id')}"))
    if img and img.get("file_id"):
        return img["file_id"]
    iso = (country.get("iso_code") or "ir").lower()
    return f"https://flagcdn.com/w640/{iso}.png"


async def announce_statement(bot, text: str, country: dict, gov: dict | None = None) -> None:
    """اعلان بیانیه رسمی کشور در کانال همراه با عکس بیانیه/پرچم رسمی و دکمه ورود به ربات."""
    channel = await get_setting("announcement_channel", "")
    if not channel:
        return
    # اگر ادمین برای بخش «بیانیه» عکسی گذاشته باشد همان استفاده می‌شود
    if await get_image("statement"):
        await send_with_image(bot, channel, text, "statement")
        return
    username = await get_channel_bot_username(bot)
    footer = f"\n\n🎮 <b>ورود به ربات:</b> @{username}"
    full_text = text if f"@{username}" in text else (text + footer)
    rm = channel_entry_markup(username)

    # 1. جستجوی عکس پرچم: اول flag_url تنظیم شده توسط کاربر/ادمین، سپس کتابخانه تصاویر، سپس flagcdn
    photo = await get_country_flag_photo(country)

    sent = False
    if photo:
        try:
            caption = full_text[:1024]
            await bot.send_photo(channel, photo, caption=caption, reply_markup=rm)
            sent = True
        except Exception:
            pass

    if not sent:
        try:
            await bot.send_message(channel, full_text, reply_markup=rm)
        except Exception:
            try:
                await bot.send_message(channel, full_text)
            except Exception:
                pass


async def image_list_text() -> tuple[str, list[list[tuple[str, str]]]]:
    """فهرست تصاویر برای پنل ادمین: (متن، دکمه‌ها)."""
    rows_db = await db.fetchall("SELECT * FROM images ORDER BY section, name")
    lines = ["🖼 <b>کتابخانه تصاویر</b>\n"]
    buttons = []
    if not rows_db:
        lines.append("— خالی است — با دکمه «➕ افزودن تصویر» اولین عکس را بفرستید.")
    for r in rows_db:
        sec = IMAGE_SECTIONS.get(r["section"], r["section"])
        lines.append(f"• <b>{r['name']}</b> — {sec} <code>#{r['id']}</code>")
        buttons.append([(f"🖼 {r['name']} ({sec})", f"a|imgv|{r['id']}")])
    return "\n".join(lines), buttons
