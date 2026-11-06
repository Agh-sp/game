"""ابزارهای مشترک ربات اصلی: کیبوردها، گاردها و نمایش کشور.

نکته مهم: تابع kb() به‌طور خودکار دکمه «🏰 بازگشت به امپراطوری من» را
زیر همه پیام‌های ربات اضافه می‌کند (اگر خودش تکراری نباشد).
"""
import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.db import db, get_setting
from core.economy import army_power, get_country, get_state, my_gov_religion
from core.firebase import fb
from core.utils import fmt, fmt_money, hours_left, fmt_hm, is_past

log = logging.getLogger(__name__)

# ─── ساخت کیبورد ───

HOME_BTN = ("🏰 بازگشت به امپراطوری من", "g|emp")
MAIN_BTN = ("🏠 منوی شروع", "g|main")


def kb(rows: list, home: bool = False) -> InlineKeyboardMarkup:
    """ساخت اینلاین کیبورد: [(متن، کالبک), ...]

    home=True → فقط در زیربخش‌های اختصاصی امپراطوری اضافه می‌شود.
    """
    clean_keyboard: list[list[InlineKeyboardButton]] = []
    has_home = False

    for r in rows:
        if not r:
            continue
        if isinstance(r, tuple) and len(r) >= 2 and isinstance(r[0], str):
            btn = _make_btn(r)
            if btn.callback_data == "g|emp":
                has_home = True
            clean_keyboard.append([btn])
        elif isinstance(r, (list, tuple)):
            btn_row: list[InlineKeyboardButton] = []
            for item in r:
                if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[0], str):
                    btn = _make_btn(item)
                    if btn.callback_data == "g|emp":
                        has_home = True
                    btn_row.append(btn)
                elif isinstance(item, InlineKeyboardButton):
                    if item.callback_data == "g|emp":
                        has_home = True
                    btn_row.append(item)
            if btn_row:
                clean_keyboard.append(btn_row)

    if home and not has_home:
        clean_keyboard.append([InlineKeyboardButton(text=HOME_BTN[0], callback_data=HOME_BTN[1])])

    return InlineKeyboardMarkup(inline_keyboard=clean_keyboard)


def empire_sub_kb(rows: list) -> InlineKeyboardMarkup:
    """ساخت کیبورد برای زیرمجموعه‌های واقعی امپراطوری با دکمه اختصاصی بازگشت به امپراطوری."""
    clean_rows = [r for r in rows if r]
    clean_rows.append([HOME_BTN])
    return kb(clean_rows, home=False)


def _make_btn(item: tuple) -> InlineKeyboardButton:
    text = item[0]
    data = item[1]
    if len(item) >= 3 and item[2] == "url":
        return InlineKeyboardButton(text=text, url=data)
    if isinstance(data, str) and (data.startswith("http://") or data.startswith("https://") or data.startswith("tg://")):
        return InlineKeyboardButton(text=text, url=data)
    return InlineKeyboardButton(text=text, callback_data=str(data))


def back_row(callback: str, text: str = "◀️ بازگشت") -> list[tuple[str, str]]:
    return [(text, callback)]


def home_row() -> list[tuple[str, str]]:
    return [("🏠 منو شروع", "g|main")]


async def safe_edit(target, text: str, reply_markup=None):
    """ویرایش امن پیام: خطای «تغییر نکرده» را نادیده می‌گیرد و در صورت خطای
    تجزیه HTML، پیام را بدون فرمت یا به‌صورت پیام تازه می‌فرستد.

    target می‌تواند CallbackQuery یا Message باشد.
    """
    msg = getattr(target, "message", target)
    try:
        await msg.edit_text(text, reply_markup=reply_markup)
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        try:
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode=None)
            return True
        except Exception:
            pass
        try:
            await msg.answer(text, reply_markup=reply_markup)
            return True
        except Exception:
            try:
                await msg.answer(text, reply_markup=reply_markup, parse_mode=None)
                return True
            except Exception:
                return False


async def send_home(message, text: str, **kw):
    """ارسال پیام متنی با کیبورد تمیز."""
    rm = kw.pop("reply_markup", None)
    if rm is None:
        rm = kb([])
    return await message.answer(text, reply_markup=rm, **kw)


async def dm(bot, chat_id, text: str, **kw):
    """ارسال پیام خصوصی به بازیکن دیگر بدون مسدودی."""
    rm = kw.pop("reply_markup", None)
    if rm is None:
        rm = kb([])
    try:
        return await bot.send_message(chat_id, text, reply_markup=rm, **kw)
    except Exception as e:
        try:
            return await bot.send_message(chat_id, text, reply_markup=rm, parse_mode=None, **kw)
        except Exception as e2:
            log.warning("dm failed to %s: %s | plain retry: %s", chat_id, e, e2)
            return None


# ─── عضویت اجباری منعطف (بدون کرش در صورت نبود کانال) ───


async def check_membership(bot, user_id: int) -> bool:
    channels = await get_setting("join_channels", "[]")
    if not channels or channels in ("[]", "", '""'):
        return True
    import json
    try:
        chans = json.loads(channels)
    except Exception:
        return True
    if not isinstance(chans, list) or not chans:
        return True
    for ch in chans:
        try:
            if not ch or not str(ch).strip():
                continue
            member = await bot.get_chat_member(chat_id=str(ch).strip(), user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            # اگر کانال وجود ندارد یا ربات ادمین نیست، مانع بازی نشود
            continue
    return True


async def join_keyboard() -> InlineKeyboardMarkup:
    import json
    chans = []
    try:
        raw = await get_setting("join_channels", "[]")
        chans = json.loads(raw) if raw else []
    except Exception:
        chans = []
    if not chans:
        chans = ["@WordWarWord", "@Jangjhani313"]
    rows = []
    for ch in chans:
        c_clean = str(ch).strip()
        if not c_clean:
            continue
        c_handle = c_clean.lstrip("@")
        label = "📢 کانال رسمی بازی" if "gp" not in c_handle.lower() else "👥 ابرگروه بازی"
        rows.append([(f"{label} ({c_clean})", f"https://t.me/{c_handle}", "url")])
    rows.append([("🔍 بررسی عضویت", "g|chk")])
    return kb(rows, home=False)


# ─── نمایش کشور ───


async def country_display(user_id: int, extended: bool = False) -> str:
    user = await db.fetchone("SELECT * FROM users WHERE id=?", (user_id,))
    country = await get_country(user_id)
    if not user or not country:
        return "🏳 کشور ندارید"
    state = await get_state(user_id)
    gov, rel = await my_gov_religion(user_id)
    atk, dfn, cyb = await army_power(user_id)
    flag = f"{country['flag']}"
    if gov and gov.get("flag"):
        flag = f"{country['flag']}{gov['flag']}"
    main_cur = await get_setting("main_currency", "")
    from core.politics import country_leader, revolution_status
    leader = await country_leader(country)
    rev = await revolution_status(user_id)
    lines = [
        f"{flag} <b>{country['name']}</b>",
        f"👤 بازیکن: {user['full_name'] or user['id']}",
        f"🏛 {leader['title']}: <b>{leader['name']}</b>",
        f"😊 رضایت مردم: <b>{round(state['satisfaction'] or 0)}/100</b>",
        f"💰 خزانه: <b>{fmt_money(user['money'])}</b> (💵 ارز کشور: {state.get('currency_name') or '—'}"
        + (f" | پول اصلی بازی: {main_cur}" if main_cur else "") + ")",
        f"🪙 سکه شاهی: <b>{fmt(user['royal_coins'])}</b>",
        f"👥 جمعیت: <b>{fmt(country['population'])}</b>",
        f"⚔️ حمله: <b>{fmt(atk)}</b> | 🛡 دفاع: <b>{fmt(dfn)}</b> | 🕶 سایبر: <b>{fmt(cyb)}</b>",
        f"⛪ دین: <b>{rel['name'] if rel else '—'}</b> | 🏛 حکومت: <b>{gov['name'] if gov else '—'}</b>",
    ]
    if extended:
        from core.straits import naval_power, my_straits
        lines += [
            f"⚓ قدرت دریایی: <b>{fmt(await naval_power(user_id))}</b> | تنگه‌های من: <b>{len(await my_straits(user_id))}</b>",
            f"🛢 نفت انبار: <b>{fmt(state.get('oil_stock') or 0)}</b> بشکه | مخزن زیرزمینی: <b>{fmt(country.get('oil_reserve') or 0)}</b>",
            f"⚡️ انرژی: <b>{fmt(state.get('energy') or 0)}</b> kWh | 💧 آب: <b>{fmt(state.get('water') or 0)}</b> | 🔥 گاز: <b>{fmt(state.get('gas') or 0)}</b>",
            f"🕊 دیپلماسی: <b>{round(state.get('diplomacy') or 50)}/100</b>",
        ]
    if rev["active"]:
        lines.append(f"\n🔥 <b>انقلاب فعال!</b> شدت {rev['severity']}٪ — فرصت {rev['left']} "
                     "(🏛 رهبری و انقلاب)")
    return "\n".join(lines)


def blocked_banner(state: dict) -> str:
    """پیام مسدودی ترور رهبر / تداخل سرور."""
    parts = []
    if state.get("server_jam_until") and not is_past(state["server_jam_until"]):
        parts.append(f"📡 <b>سرورهای شما در حال اختلال هستند!</b> ({fmt_hm(hours_left(state['server_jam_until']))} مانده)\n"
                     "تا رفع مشکل فقط می‌توانید بیانیه صادر کنید.")
    elif state.get("leader_block_until") and not is_past(state["leader_block_until"]):
        parts.append(f"🚫 <b>رهبر شما ترور شده!</b> ({fmt_hm(hours_left(state['leader_block_until']))} مانده)\n"
                     "حمله و دیپلماسی مسدود است.")
    return ("\n".join(parts) + "\n\n") if parts else ""


def server_line() -> str:
    """وضعیت اتصال سرور فایربیس‌مانند."""
    try:
        return fb.status_line()
    except Exception:
        return ""


# ─── منوهای اصلی ───


def _handle(value: str) -> str:
    """نرمال‌سازی آیدی کانال/گروه برای ساخت لینک t.me."""
    v = str(value or "").strip()
    if v.startswith("https://t.me/"):
        v = v[len("https://t.me/"):]
    return v.lstrip("@").strip("/")


async def channel_links() -> list[tuple[str, str, str]]:
    """دکمه‌های گپ و کانال از تنظیمات دیتابیس (نه هاردکد).

    اگر ادمین گروه/کانال را از پنل عوض کند، منوی اصلی هم فوراً همان را نشان می‌دهد.
    """
    from core import config as cfg
    group = _handle(await get_setting("game_group", "") or cfg.OFFICIAL_GROUP)
    channel = _handle(await get_setting("announcement_channel", "") or cfg.OFFICIAL_CHANNEL)
    rows: list[tuple[str, str, str]] = []
    if group:
        rows.append((f"👥 گپ بازی (@{group})", f"https://t.me/{group}", "url"))
    if channel:
        rows.append((f"📢 کانال خبری (@{channel})", f"https://t.me/{channel}", "url"))
    return rows


async def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [("🏰 امپراطوری من", "g|emp")],
        [("🎯 ماموریت روزانه", "g|mis"), ("🪙 سکه شاهی", "g|coin")],
        await channel_links(),
        [("📖 راهنمای بازی", "g|guide"), ("🛟 پشتیبانی", "g|sup")],
        [("🔄 تغییر کشور", "g|cchg")],
    ]
    rows = [r for r in rows if r]
    if is_admin:
        from core import config as cfg
        handle = _handle(getattr(cfg, "ADMIN_BOT_USERNAME", "") or "agfafagjganigagbot")
        rows.append([(f"🛡 پنل ادمین (@{handle})", f"https://t.me/{handle}", "url")])
    return kb(rows)


def empire_kb() -> InlineKeyboardMarkup:
    return kb([
        [("🏛 مدیریت کشور", "g|mg")],
        [("💵 درآمد", "g|inc"), ("🗺 استان‌ها", "g|prov")],
        [("🤝 اتحاد", "g|ally"), ("☢️ غنی‌سازی", "g|enrich")],
        [("⚔️ اتاق جنگ", "g|war")],
        [("🤝 تجارت بین‌المللی", "g|trd")],
        [("🕊 سازمان ملل", "g|un")],
        [("🛟 سازمان نجات", "g|resc")],
        [("📢 بیانیه", "g|stmt")],
        home_row(),
    ])


def manage_kb() -> InlineKeyboardMarkup:
    return kb([
        [("👥 مردم", "g|ppl")],
        [("🏗 پروژه ملی", "g|prj")],
        [("🪖 ارتش", "g|army")],
        [("⛪ دین و حکومت", "g|gov")],
        [("🏛 رهبری و انقلاب", "g|pol")],
        [("🛢 نفت و تجارت خودکار", "g|oil")],
        [("♻️ فروش منابع (برق/آب/گاز/غذا)", "g|res")],
        [("🧱 خرید مصالح ساختمانی", "g|matshop")],
        [("🏢 شرکت‌های من", "g|comp")],
        home_row(),
    ])
