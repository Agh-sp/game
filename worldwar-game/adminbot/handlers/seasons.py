"""مدیریت سیزن‌ها — حذف، تغییر اسم، تغییر مود و شروع رای‌گیری سیزن جدید در کانال.

مودها: جنگ جهانی / جنگ‌های صلیبی / جنگ‌های باستان.
رای‌گیری: بازیکن‌ها در کانال با دکمه‌های ربات اصلی رأی می‌دهند؛ هر گزینه که
زودتر به حداقل رأیِ تعیین‌شده برسد همان سیزن اجرا می‌شود.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import cd, kb
from adminbot.tools import log_action
from core.db import db, get_setting, set_setting
from core.seed import SEASON_MODES
from core.utils import add_hours, iso

router = Router()

MODE_TITLES = {k: v for k, v in SEASON_MODES.items()}


class SeasonFSM(StatesGroup):
    new_name = State()
    rename = State()
    req_votes = State()


@router.message(Command("seasons"))
async def cmd_seasons(message: Message, perms: set):
    if not has(perms, "seasons"):
        return await message.answer("⛔️ دسترسی ندارید")
    await message.answer(**await _seasons_payload())


async def _seasons_payload() -> dict:
    seasons = await db.fetchall("SELECT * FROM seasons ORDER BY id DESC LIMIT 10")
    current_name = await get_setting("season_name", "—")
    current_mode = await get_setting("season_mode", "worldwar")
    vote = await db.fetchone("SELECT * FROM season_votes WHERE status='open' ORDER BY id DESC LIMIT 1")
    lines = ["🎬 <b>مدیریت سیزن‌ها</b>\n",
             f"سیزن فعلی: <b>{current_name}</b> ({MODE_TITLES.get(current_mode, current_mode)})\n"]
    if vote:
        import json
        options = json.loads(vote["options"] or "[]")
        ballots = await db.fetchall("SELECT choice, COUNT(*) c FROM season_ballots "
                                   "WHERE vote_id=? GROUP BY choice", (vote["id"],))
        counts = {b["choice"]: b["c"] for b in ballots}
        lines.append(f"🗳 رای‌گیری باز #{vote['id']} (حد رأی: {vote['required_votes']}):")
        for i, opt in enumerate(options):
            lines.append(f"• {opt}: {counts.get(i, 0)} رأی")
        lines.append("")
    lines.append("سیزن‌های اخیر:")
    for s in seasons:
        active = "🟢" if s["is_active"] else "⚪"
        lines.append(f"{active} {s['name']} — {MODE_TITLES.get(s['mode'], s['mode'])} <code>#{s['id']}</code>")
    buttons = [
        [("🗳 شروع رای‌گیری سیزن جدید", "a|seavote")],
        [("➕ ساخت سیزن جدید", "a|seanew")],
    ]
    for s in seasons[:6]:
        if s["is_active"]:
            buttons.append([(f"✏️ تغییر اسم «{s['name'][:20]}»", f"a|searen|{s['id']}")])
            buttons.append([(f"🔀 تغییر مود «{s['name'][:20]}»", f"a|seamode|{s['id']}")])
        else:
            buttons.append([(f"🗑 حذف «{s['name'][:20]}»", f"a|seadel|{s['id']}"),
                            (f"🟢 فعال‌سازی", f"a|seaact|{s['id']}")])
    buttons.append([("◀️ بازگشت", "a|root")])
    return {"text": "\n".join(lines), "reply_markup": kb(buttons)}


@router.callback_query(F.data == "a|season")
async def seasons_menu(call: CallbackQuery, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    payload = await _seasons_payload()
    await call.answer()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data == "a|seavote")
async def season_vote_start(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.set_state(SeasonFSM.req_votes)
    await call.answer()
    await call.message.edit_text(
        "🗳 <b>رای‌گیری سیزن جدید</b>\n\nحداقل تعداد رأی برای انتخاب سیزن را بنویسید "
        "(پیش‌فرض فعلی: " + await get_setting("season_required_votes", "10") + "):\n"
        "برای انصراف /cancel",
        reply_markup=kb([[("◀️ انصراف", "a|season")]]))


@router.message(SeasonFSM.req_votes)
async def season_vote_create(message: Message, state: FSMContext):
    try:
        req = int((message.text or "").strip())
    except ValueError:
        return await message.answer("❌ فقط عدد بفرستید.")
    if req < 1:
        return await message.answer("❌ حداقل ۱.")
    await state.clear()
    hours = float(await get_setting("season_vote_hours", "24"))
    options = list(MODE_TITLES.values())
    import json
    vid = await db.execute(
        "INSERT INTO season_votes(options, required_votes, ends_at) VALUES(?,?,?)",
        (json.dumps(options, ensure_ascii=False), req, add_hours(hours)))
    await set_setting("season_required_votes", str(req))
    await log_action(message.from_user.id, "سیزن", f"رای‌گیری #{vid} با حد رأی {req}")
    await message.answer(
        f"✅ رای‌گیری سیزن جدید #{vid} ساخته شد (حد رأی: {req}).\n"
        "🗳 پیام رای‌گیری به‌زودی توسط ربات اصلی در کانال اعلانات گذاشته می‌شود "
        "و هر گزینه که زودتر به حد رأی برسد همان سیزن اجرا خواهد شد.")
    payload = await _seasons_payload()
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data == "a|seanew")
async def season_new(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.set_state(SeasonFSM.new_name)
    await call.answer()
    await call.message.edit_text("➕ نام سیزن جدید را بنویسید:\n برای انصراف /cancel",
                                 reply_markup=kb([[("◀️ انصراف", "a|season")]]))


@router.message(SeasonFSM.new_name)
async def season_new_input(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 60:
        return await message.answer("❌ نام باید بین ۱ تا ۶۰ حرف باشد.")
    await state.clear()
    await db.execute("UPDATE seasons SET is_active=0")
    sid = await db.execute("INSERT INTO seasons(name, mode, is_active) VALUES(?,? ,1)",
                           (name, "worldwar"))
    await set_setting("season_name", name)
    await set_setting("season_mode", "worldwar")
    await log_action(message.from_user.id, "سیزن", f"ساخت {name} #{sid}")
    await message.answer(f"✅ سیزن «{name}» ساخته و فعال شد (مود: جنگ جهانی ۳).")
    payload = await _seasons_payload()
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data.startswith("a|searen|"))
async def season_rename(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    sid = int(call.data.split("|")[2])
    await state.set_state(SeasonFSM.rename)
    await state.update_data(season_id=sid)
    await call.answer()
    await call.message.edit_text("✏️ نام جدید سیزن را بنویسید:\n برای انصراف /cancel")


@router.message(SeasonFSM.rename)
async def season_rename_input(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 60:
        return await message.answer("❌ نام باید بین ۱ تا ۶۰ حرف باشد.")
    data = await state.get_data()
    await state.clear()
    await db.execute("UPDATE seasons SET name=? WHERE id=?", (name, data["season_id"]))
    s = await db.fetchone("SELECT * FROM seasons WHERE id=?", (data["season_id"],))
    if s and s["is_active"]:
        await set_setting("season_name", name)
    await log_action(message.from_user.id, "سیزن", f"تغییر نام #{data['season_id']} → {name}")
    await message.answer(f"✅ نام سیزن به «{name}» تغییر کرد.")
    payload = await _seasons_payload()
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data.startswith("a|seamode|"))
async def season_change_mode(call: CallbackQuery, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    sid = int(call.data.split("|")[2])
    rows = []
    for mode, title in MODE_TITLES.items():
        rows.append([(f"🎬 {title}", f"a|seamodeset|{sid}|{mode}")])
    rows.append([("◀️ بازگشت", "a|season")])
    await call.answer()
    await call.message.edit_text("🔀 مود جدید این سیزن را انتخاب کنید:", reply_markup=kb(rows))


@router.callback_query(F.data.startswith("a|seamodeset|"))
async def season_mode_set(call: CallbackQuery, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, sid, mode = call.data.split("|")
    await db.execute("UPDATE seasons SET mode=? WHERE id=?", (mode, int(sid)))
    s = await db.fetchone("SELECT * FROM seasons WHERE id=?", (int(sid),))
    if s and s["is_active"]:
        await set_setting("season_mode", mode)
        await set_setting("season_name", MODE_TITLES.get(mode, s["name"]))
        await db.execute("UPDATE seasons SET name=? WHERE id=?", (MODE_TITLES.get(mode, s["name"]), int(sid)))
    await log_action(call.from_user.id, "سیزن", f"مود #{sid} → {mode}")
    await call.answer("✅ مود تغییر کرد")
    await seasons_menu(call, perms)


@router.callback_query(F.data.startswith("a|seadel|"))
async def season_delete(call: CallbackQuery, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    sid = int(call.data.split("|")[2])
    s = await db.fetchone("SELECT * FROM seasons WHERE id=?", (sid,))
    if not s:
        return await call.answer("یافت نشد", show_alert=True)
    if s["is_active"]:
        return await call.answer("❌ سیزن فعال را نمی‌توان حذف کرد — اول سیزن جدید بسازید", show_alert=True)
    await db.execute("DELETE FROM seasons WHERE id=?", (sid,))
    await log_action(call.from_user.id, "سیزن", f"حذف #{sid}")
    await call.answer("🗑 حذف شد")
    await seasons_menu(call, perms)


@router.callback_query(F.data.startswith("a|seaact|"))
async def season_activate(call: CallbackQuery, perms: set):
    if not has(perms, "seasons"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    sid = int(call.data.split("|")[2])
    s = await db.fetchone("SELECT * FROM seasons WHERE id=?", (sid,))
    if not s:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE seasons SET is_active=0")
    await db.execute("UPDATE seasons SET is_active=1 WHERE id=?", (sid,))
    await set_setting("season_name", s["name"])
    await set_setting("season_mode", s["mode"])
    await log_action(call.from_user.id, "سیزن", f"فعال‌سازی {s['name']}")
    await call.answer("✅ فعال شد")
    await seasons_menu(call, perms)
