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
    "war": "⚔️ جنگ و نبرد",
    "general": "📦 عمومی",
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


async def send_with_image(bot, chat_id: str | int, text: str,
                          section: str = "", name: str = "") -> None:
    """ارسال پیام به چت/کانال — اگر عکس بخش موجود بود با عکس (کپشن)، وگرنه متن."""
    img = await get_image(section, name)
    try:
        if img and img["file_id"]:
            await bot.send_photo(chat_id, img["file_id"], caption=text[:1000])
        else:
            await bot.send_message(chat_id, text)
    except Exception:
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            pass


async def announce_img(bot, text: str, section: str = "", name: str = "") -> None:
    """اعلان کانال همراه عکس کتابخانه (در صورت وجود)."""
    channel = await get_setting("announcement_channel", "")
    if not channel:
        return
    await send_with_image(bot, channel, text, section, name)


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
