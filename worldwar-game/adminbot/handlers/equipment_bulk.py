"""ساخت جمعی تجهیزات نظامی — فرمت هر خط: اسم-سرعت-قدرت تهاجمی-قدرت دفاعی-قیمت.

برای هر دسته‌بندی متفاوت است؛ قیمت عددی = پول و اگر با c تمام شود = سکه شاهی.
ساخت/ویرایش/حذف تکی از همان موتور CRUD (موجودیت تجهیزات) انجام می‌شود.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import kb
from adminbot.tools import log_action
from core.db import db
from core.utils import fmt

router = Router()


class BulkFSM(StatesGroup):
    lines = State()


@router.message(Command("bulkeq"))
async def cmd_bulkeq(message: Message, perms: set):
    if not has(perms, "military"):
        return await message.answer("⛔️ دسترسی ندارید")
    cats = await db.fetchall("SELECT * FROM equipment_categories WHERE is_active=1 ORDER BY id")
    rows = [[(f"{c['emoji']} {c['title']}", f"a|bulkcat|{c['id']}")] for c in cats]
    rows.append([("◀️ بازگشت", "a|root")])
    await message.answer(
        "🪖 <b>ساخت جمعی تجهیزات</b>\n\nدسته‌بندی را انتخاب کنید.\n"
        "فرمت هر خط (با خط تیره جدا شود):\n"
        "<code>اسم-سرعت-قدرت تهاجمی-قدرت دفاعی-قیمت</code>\n"
        "مثال: <code>موشک کروز-4-2000-0-150000000</code>\n"
        "💡 قیمت اگر با c تمام شود سکه شاهی است: <code>پهپاد شناسا-5-300-100-50c</code>",
        reply_markup=kb(rows))


@router.callback_query(F.data == "a|bulk")
async def bulk_menu(call: CallbackQuery, perms: set):
    if not has(perms, "military"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    cats = await db.fetchall("SELECT * FROM equipment_categories WHERE is_active=1 ORDER BY id")
    rows = [[(f"{c['emoji']} {c['title']}", f"a|bulkcat|{c['id']}")] for c in cats]
    rows.append([("◀️ بازگشت", "a|root")])
    await call.answer()
    await call.message.edit_text(
        "🪖 <b>ساخت جمعی تجهیزات</b>\n\nدسته‌بندی را انتخاب کنید.\n"
        "فرمت هر خط: <code>اسم-سرعت-قدرت تهاجمی-قدرت دفاعی-قیمت</code>\n"
        "مثال: <code>موشک کروز-4-2000-0-150000000</code> یا با سکه: <code>پهپاد شناسا-5-300-100-50c</code>",
        reply_markup=kb(rows))


@router.callback_query(F.data.startswith("a|bulkcat|"))
async def bulk_category(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "military"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    cid = int(call.data.split("|")[2])
    cat = await db.fetchone("SELECT * FROM equipment_categories WHERE id=?", (cid,))
    if not cat:
        return await call.answer("یافت نشد", show_alert=True)
    await state.set_state(BulkFSM.lines)
    await state.update_data(bulk_cat=cid)
    await call.answer()
    await call.message.edit_text(
        f"🪖 ساخت جمعی در دسته «{cat['emoji']} {cat['title']}»\n\n"
        "هر خط یک تجهیز — فرمت:\n"
        "<code>اسم-سرعت-قدرت تهاجمی-قدرت دفاعی-قیمت</code>\n"
        "(سرعت ۱ تا ۵ | قیمت عدد=پول، عددc=سکه)\n\n"
        "همه خطوط را یکجا بفرستید:\n برای انصراف /cancel",
        reply_markup=kb([[("◀️ انصراف", "a|bulk")]]))


@router.message(BulkFSM.lines)
async def bulk_lines_input(message: Message, state: FSMContext):
    data = await state.get_data()
    cat_id = data.get("bulk_cat")
    cat = await db.fetchone("SELECT * FROM equipment_categories WHERE id=?", (cat_id,))
    if not cat:
        await state.clear()
        return await message.answer("❌ دسته یافت نشد — دوباره شروع کنید.")
    lines = [l.strip() for l in (message.text or "").splitlines() if l.strip()]
    if not lines:
        return await message.answer("❌ حداقل یک خط لازم است.")
    created, errors = [], []
    for i, line in enumerate(lines, 1):
        parts = [p.strip() for p in line.split("-")]
        if len(parts) != 5:
            errors.append(f"خط {i}: فرمت ناقص")
            continue
        name, speed, atk, dfn, price = parts
        try:
            speed_i = int(speed)
            atk_i = int(atk)
            dfn_i = int(dfn)
            if not 1 <= speed_i <= 5:
                raise ValueError
        except ValueError:
            errors.append(f"خط {i}: سرعت باید ۱-۵ و قدرت‌ها عدد باشند")
            continue
        coins = price.lower().endswith("c")
        price_txt = price[:-1].strip() if coins else price
        try:
            price_i = int(price_txt.replace(",", ""))
        except ValueError:
            errors.append(f"خط {i}: قیمت نامعتبر")
            continue
        await db.execute(
            "INSERT INTO equipment(category_id, name, emoji, attack_power, defense_power, "
            "speed, price_money, price_coins) VALUES(?,?,?,?,?,?,?,?)",
            (cat_id, name, cat["emoji"], atk_i, dfn_i, speed_i,
             0 if coins else price_i, price_i if coins else 0))
        created.append(name)
    await state.clear()
    await log_action(message.from_user.id, "تجهیزات",
                     f"ساخت جمعی {len(created)} عدد در {cat['title']}")
    text = (f"✅ <b>{len(created)}</b> تجهیز در دسته «{cat['title']}» ساخته شد:\n"
            + "\n".join(f"• {n}" for n in created[:20]))
    if errors:
        text += "\n\n⚠️ خطاها:\n" + "\n".join(errors[:10])
    await message.answer(text)
    await bulk_menu(_fake_call(message), set())


class _fake_call:
    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, *_a, **_k):
        pass
