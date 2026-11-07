"""🎯 خرابکاری در تأسیسات — زدن هر چیزی که دشمن ساخته است.

بخش «🎯 خرابکاری در تأسیسات» در اتاق جنگ:

    g|sab          → فهرست کشورهای دارای سازه
    g|sabd|<uid>   → فهرست سازه‌های آن کشور
    g|sabv|<kind>|<item>|<uid> → پیش‌نمایش شانس اصابت
    g|sabgo|<kind>|<item>|<uid> → اجرای حمله
    g|sabmy        → خسارت‌های واردشده به کشور خودم
    g|sabfix       → بازسازی سازه‌های آسیب‌دیده

همهٔ اعداد از پنل ادمین (`sabotage_*`) قابل تغییرند.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from core.db import db
from core.utils import fmt
from gamebot.common import back_row, kb

log = logging.getLogger(__name__)
router = Router()

GROUP_ORDER = [
    ("nuclear", "☢️ هسته‌ای"),
    ("oil", "🛢 نفت"),
    ("industry", "🏭 پالایش و مخازن"),
    ("power", "⚡ برق"),
    ("water", "💧 آب"),
    ("gas", "🔥 گاز"),
    ("airdef", "🎖 پدافند"),
    ("company", "🏢 شرکت‌ها"),
    ("internet", "🌐 اینترنت"),
]


def _kind_title(kind: str) -> str:
    from core.sabotage import TARGET_KINDS
    return TARGET_KINDS.get(kind, {}).get("title", kind)


@router.callback_query(F.data == "g|sab")
async def sabotage_menu(call: CallbackQuery):
    """فهرست کشورهایی که سازهٔ قابل هدف دارند."""
    from core import sabotage

    if await _blocked(call):
        return
    rows_list = await sabotage.targets_summary(call.from_user.id)
    left = await sabotage.cooldown_left(call.from_user.id)

    lines = [
        "🎯 <b>خرابکاری در تأسیسات دشمن</b>\n",
        "هر چیزی که دشمن ساخته است هدف است: ☢️ تأسیسات هسته‌ای، 🛢 دکل نفتی، "
        "⚡ نیروگاه، 💧 آب، 🔥 گاز، 🏭 پالایشگاه، 🏢 شرکت، 🌐 اینترنت و 🎖 پدافند.\n",
        "🛡 هر سازه پدافند خودش را دارد؛ اگر پدافند دشمن قوی باشد حمله رهگیری می‌شود.\n",
    ]
    if left:
        lines.append(f"⏱ <b>کول‌داون:</b> {left} دقیقه تا خرابکاری بعدی.\n")

    rows = []
    if not rows_list:
        lines.append("— هیچ کشوری سازهٔ قابل هدف ندارد —")
    for t in rows_list[:10]:
        parts = [f"{title}: {fmt(t['counts'][kind])}"
                 for kind, title in GROUP_ORDER if t["counts"].get(kind)]
        lines.append(f"{t['flag']} <b>{t['name']}</b> — " + " | ".join(parts))
        rows.append([(f"🎯 سازه‌های {t['flag']} {t['name']}", f"g|sabd|{t['user_id']}")])

    rows.append([("📋 خسارت‌های وارده به من", "g|sabmy"),
                 ("🔧 بازسازی سازه‌ها", "g|sabfix")])
    rows.append(back_row("g|war"))
    await call.answer()
    # 💡 همهٔ دکمه‌ها را در متن هم بنویسیم تا در هر کلاینتی دیده شوند
    if rows_list:
        lines.append("\n💡 کشور هدف را انتخاب کنید:")
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))
    except Exception:
        await call.message.answer("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|sabd|"))
async def sabotage_targets(call: CallbackQuery):
    """فهرست سازه‌های یک کشور برای انتخاب هدف."""
    from core import sabotage

    if await _blocked(call):
        return
    defender_id = int(call.data.split("|")[2])
    if defender_id == call.from_user.id:
        return await call.answer("❌ نمی‌توانید کشور خودتان را هدف بگیرید.", show_alert=True)

    facs = await sabotage.facilities(defender_id)
    text = await sabotage.targets_text(call.from_user.id, defender_id)
    rows = []
    for f in facs[:24]:
        label = f"{f['emoji']} {f['name']}"
        if int(f["qty"]) > 1:
            label += f" ×{fmt(f['qty'])}"
        rows.append([(label, f"g|sabv|{f['kind']}|{int(f['item_id'])}|{defender_id}")])
    rows.append([("◀️ بازگشت به فهرست کشورها", "g|sab")])
    await call.answer()
    try:
        await call.message.edit_text(text, reply_markup=kb(rows))
    except Exception:
        await call.message.answer(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|sabv|"))
async def sabotage_preview(call: CallbackQuery):
    """پیش‌نمایش شانس اصابت به یک سازه."""
    from core import sabotage
    from core.economy import get_country

    if await _blocked(call):
        return
    _, _, kind, item_id, defender_id = call.data.split("|")
    defender_id, item_id = int(defender_id), int(item_id)

    look = await sabotage.outlook(call.from_user.id, defender_id, kind, item_id)
    if not look.get("ok"):
        return await call.answer(look.get("error") or "هدف یافت نشد", show_alert=True)

    fac, info = look["facility"], look["info"]
    c = await get_country(defender_id)
    ok, err = await sabotage.can_sabotage(call.from_user.id, kind)
    left = await sabotage.cooldown_left(call.from_user.id)

    lines = [
        f"{info['emoji']} <b>هدف: {fac['name']}</b>",
        f"🏳 کشور: {c['flag']} <b>{c['name']}</b>" if c else "🏳 کشور: —",
        f"📦 موجودی: <b>{fmt(fac['qty'])}</b>",
        "",
        f"🎯 اثر تخریب: {info['desc']}",
        "",
        f"🚀 توان حمله شما: <b>{fmt(look['atk'])}</b>",
        f"🛡 پدافند هدف: <b>{fmt(look['def'])}</b>",
        f"🎲 احتمال اصابت: <b>{look['chance']}%</b>",
    ]
    if left:
        lines.append(f"⏱ کول‌داون: <b>{left}</b> دقیقه مانده")
    if not ok:
        lines.append("\n" + err)

    rows = []
    if ok:
        rows.append([(f"🎯 شلیک کن ({look['chance']}%)",
                      f"g|sabgo|{kind}|{item_id}|{defender_id}")])
    rows.append([("◀️ بازگشت به سازه‌های این کشور", f"g|sabd|{defender_id}")])
    await call.answer()
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))
    except Exception:
        await call.message.answer("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|sabgo|"))
async def sabotage_execute(call: CallbackQuery):
    """اجرای خرابکاری و نمایش گزارش واقعی."""
    from core import sabotage

    if await _blocked(call):
        return
    _, _, kind, item_id, defender_id = call.data.split("|")
    defender_id, item_id = int(defender_id), int(item_id)

    await call.answer("🚀 در حال شلیک…")
    report = await sabotage.sabotage(call.bot, call.from_user.id, defender_id,
                                     kind, item_id)
    rows = [
        [("🎯 هدف بعدی در همین کشور", f"g|sabd|{defender_id}")],
        [("◀️ بخش خرابکاری", "g|sab")],
    ]
    try:
        await call.message.edit_text(report, reply_markup=kb(rows))
    except Exception:
        await call.message.answer(report, reply_markup=kb(rows))


@router.callback_query(F.data == "g|sabmy")
async def sabotage_my_damage(call: CallbackQuery):
    """📋 خسارت‌هایی که به کشور من وارد شده."""
    from core import sabotage

    text = await sabotage.my_damage_text(call.from_user.id)
    await call.answer()
    try:
        await call.message.edit_text(text, reply_markup=kb([
            [("🔧 بازسازی سازه‌ها", "g|sabfix")],
            back_row("g|sab"),
        ]))
    except Exception:
        await call.message.answer(text, reply_markup=kb([back_row("g|sab")]))


@router.callback_query(F.data == "g|sabfix")
async def sabotage_rebuild_menu(call: CallbackQuery):
    """🔧 فهرست سازه‌های قابل بازسازی."""
    from core import sabotage

    opts = await sabotage.rebuild_options(call.from_user.id)
    lines = [
        "🔧 <b>بازسازی سازه‌های آسیب‌دیده</b>\n",
        "هر سازه با <b>نصف قیمت ساخت</b> و کمی مصالح بازسازی می‌شود:\n",
    ]
    rows = []
    if not opts:
        lines.append("— هیچ سازهٔ آسیب‌دیده‌ای برای بازسازی نیست —")
    for o in opts[:12]:
        lines.append(f"• {o['title']} — 💰 {fmt(o['cost_money'])} | "
                     f"🧱 {fmt(o.get('cost_mats') or 0)} مصالح")
        rows.append([(f"🔧 {o['title']}",
                      f"g|sabfixgo|{o['kind']}|{int(o.get('item_id') or 0)}")])
    rows.append(back_row("g|sab"))
    await call.answer()
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(rows))
    except Exception:
        await call.message.answer("\n".join(lines), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("g|sabfixgo|"))
async def sabotage_rebuild_do(call: CallbackQuery):
    """اجرای بازسازی یک سازه."""
    from core import sabotage

    _, _, kind, item_id = call.data.split("|")
    ok, msg = await sabotage.rebuild(call.from_user.id, kind, int(item_id))
    await call.answer("✅ بازسازی شد" if ok else "⚠️ انجام نشد", show_alert=not ok)
    try:
        await call.message.edit_text(msg, reply_markup=kb([
            [("🔧 بازسازی دیگر", "g|sabfix")],
            back_row("g|sab"),
        ]))
    except Exception:
        await call.message.answer(msg, reply_markup=kb([back_row("g|sab")]))


async def _blocked(call: CallbackQuery) -> bool:
    """قفل‌های عمومی: خلع سلاح و اختلال سرور."""
    from core.economy import is_disarmed, is_jammed

    if await is_disarmed(call.from_user.id):
        await call.answer("🕊 خلع سلاح شده‌اید — حمله ممکن نیست!", show_alert=True)
        return True
    if await is_jammed(call.from_user.id):
        await call.answer("📡 سرورهای شما اختلال دارند!", show_alert=True)
        return True
    return False
