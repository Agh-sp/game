"""مدیریت ادمین‌ها (فقط سوپرادمین): افزودن، سطح دسترسی، حذف."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import ALL_PERMS, PERM_TITLES
from adminbot.crud import cd, kb
from adminbot.tools import log_action, notify_user
from core.db import db
from core.utils import jloads, jdumps, fmt

router = Router()


class AdminFSM(StatesGroup):
    add_id = State()
    add_name = State()


def is_super(admin: dict) -> bool:
    return bool(admin and admin.get("is_super"))


@router.callback_query(F.data == "a|adm")
async def admins_menu(call: CallbackQuery, admin: dict, perms: set):
    if not is_super(admin):
        return await call.answer("⛔️ فقط سوپرادمین!", show_alert=True)
    rows = await db.fetchall("SELECT * FROM admins ORDER BY is_super DESC, id")
    lines = ["🛡 <b>ادمین‌ها</b>\n"]
    buttons = []
    for a in rows:
        perm_count = "همه (سوپر)" if a["is_super"] else f"{len(jloads(a['perms'], []))} دسترسی"
        lines.append(f"{'👑' if a['is_super'] else '🛡'} {a['name'] or '—'} <code>{a['id']}</code> — {perm_count}")
        if not a["is_super"]:
            buttons.append([(f"🛡 {a['name'] or a['id']}", f"a|admo|{a['id']}")])
    buttons.append([("➕ افزودن ادمین", "a|admadd")])
    buttons.append([("◀️ بازگشت", "a|root")])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("a|admo|"))
async def admin_options(call: CallbackQuery, admin: dict):
    if not is_super(admin):
        return await call.answer("⛔️ فقط سوپرادمین!", show_alert=True)
    aid = int(call.data.split("|")[2])
    target = await db.fetchone("SELECT * FROM admins WHERE id=?", (aid,))
    if not target or target["is_super"]:
        return await call.answer("یافت نشد", show_alert=True)
    perms = set(jloads(target["perms"], []))
    lines = [
        f"🛡 <b>ادمین: {target['name'] or '—'}</b> — <code>{target['id']}</code>\n",
        "دسترسی‌ها (روی هرکدام بزنید تا فعال/غیرفعال شود):",
    ]
    buttons = []
    row = []
    for p in ALL_PERMS:
        on = p in perms
        row.append((f"{'✅' if on else '❌'} {PERM_TITLES[p]}", f"a|admp|{aid}|{p}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([("🗑 حذف ادمین", f"a|admd|{aid}")])
    buttons.append([("◀️ بازگشت", "a|adm")])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("a|admp|"))
async def admin_toggle_perm(call: CallbackQuery, admin: dict):
    if not is_super(admin):
        return await call.answer("⛔️ فقط سوپرادمین!", show_alert=True)
    _, _, aid, perm = call.data.split("|")
    target = await db.fetchone("SELECT * FROM admins WHERE id=?", (int(aid),))
    if not target or target["is_super"]:
        return await call.answer("یافت نشد", show_alert=True)
    perms = set(jloads(target["perms"], []))
    if perm in perms:
        perms.remove(perm)
    else:
        perms.add(perm)
    await db.execute("UPDATE admins SET perms=? WHERE id=?", (jdumps(sorted(perms)), int(aid)))
    await log_action(call.from_user.id, "ادمین", f"دسترسی {perm} → {int(aid)}")
    await call.answer("✅ تغییر کرد")
    await admin_options(call, admin)


@router.callback_query(F.data.startswith("a|admd|"))
async def admin_remove(call: CallbackQuery, admin: dict):
    if not is_super(admin):
        return await call.answer("⛔️ فقط سوپرادمین!", show_alert=True)
    aid = int(call.data.split("|")[2])
    target = await db.fetchone("SELECT * FROM admins WHERE id=?", (aid,))
    if not target or target["is_super"]:
        return await call.answer("سوپرادمین حذف نمی‌شود", show_alert=True)
    await db.execute("DELETE FROM admins WHERE id=?", (aid,))
    await log_action(call.from_user.id, "ادمین", f"حذف ادمین {aid}")
    await notify_user(aid, "⛔️ دسترسی ادمین شما حذف شد.")
    await call.answer("🗑 حذف شد")
    await admins_menu(call, admin, set())


@router.callback_query(F.data == "a|admadd")
async def admin_add(call: CallbackQuery, admin: dict, state: FSMContext):
    if not is_super(admin):
        return await call.answer("⛔️ فقط سوپرادمین!", show_alert=True)
    await state.set_state(AdminFSM.add_id)
    await call.answer()
    await call.message.edit_text(
        "➕ <b>افزودن ادمین</b>\n\n🆔 آیدی عددی تلگرام ادمین جدید را بفرستید:\n"
        "💡 او می‌تواند آیدی خود را از @userinfobot بگیرد.\n برای انصراف /cancel")


@router.message(AdminFSM.add_id)
async def admin_add_id(message: Message, state: FSMContext, admin: dict):
    if not is_super(admin):
        return
    try:
        aid = int((message.text or "").strip())
    except ValueError:
        return await message.answer("❌ فقط آیدی عددی بفرستید.")
    exists = await db.fetchone("SELECT id FROM admins WHERE id=?", (aid,))
    if exists:
        return await message.answer("❌ این آیدی قبلاً ادمین است.")
    await state.update_data(new_admin_id=aid)
    await state.set_state(AdminFSM.add_name)
    await message.answer("👤 نام یا توضیح این ادمین را بفرستید:")


@router.message(AdminFSM.add_name)
async def admin_add_name(message: Message, state: FSMContext, admin: dict):
    if not is_super(admin):
        return
    data = await state.get_data()
    name = (message.text or "").strip()[:50] or "ادمین"
    await state.clear()
    await db.execute(
        "INSERT INTO admins(id, name, is_super, perms, added_by) VALUES(?,?,0,'[]',?)",
        (data["new_admin_id"], name, message.from_user.id))
    await log_action(message.from_user.id, "ادمین", f"افزودن {data['new_admin_id']} ({name})")
    await notify_user(data["new_admin_id"],
                      f"🛡 تبریک! شما ادمین ربات «جنگ جهانی» شدید. ربات ادمین را استارت کنید.")
    await message.answer(
        f"✅ ادمین <b>{name}</b> (<code>{data['new_admin_id']}</code>) اضافه شد.\n\n"
        "حالا از منوی 🛡 ادمین‌ها سطح دسترسی‌هایش را تعیین کنید.")
    fake = _FakeCall(message)
    await admins_menu(fake, admin, set())


class _FakeCall:
    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, *_a, **_k):
        pass
