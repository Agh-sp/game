"""کتابخانه تصاویر دائمی — ارسال عکس برای بخش‌های مختلف + نامگذاری.

هر عکس یک «اسم» می‌گیرد و در دیتابیس دائمی ذخیره می‌شود؛
بازی هر جا نیاز به عکس بخشی داشت (پیمان/مذاکره/تنگه/ارز/...) از همین
کتابخانه با اسم یا بخش استفاده می‌کند.
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
from core.images import IMAGE_SECTIONS, get_image, image_list_text

router = Router()


class ImgFSM(StatesGroup):
    name = State()
    section = State()
    photo = State()


SECTIONS_ROWS = [[(title, f"a|imgsec|{key}")] for key, title in IMAGE_SECTIONS.items()]


@router.message(Command("images"))
async def cmd_images(message: Message, perms: set):
    if not has(perms, "media"):
        return await message.answer("⛔️ دسترسی ندارید")
    text, buttons = await image_list_text()
    buttons.append([("➕ افزودن تصویر", "a|imgnew")])
    buttons.append([("◀️ بازگشت", "a|root")])
    await message.answer(text, reply_markup=kb(buttons))


@router.callback_query(F.data == "a|img")
async def images_menu(call: CallbackQuery, perms: set):
    if not has(perms, "media"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    text, buttons = await image_list_text()
    buttons.append([("➕ افزودن تصویر", "a|imgnew")])
    buttons.append([("◀️ بازگشت", "a|root")])
    await call.answer()
    await call.message.edit_text(text, reply_markup=kb(buttons))


@router.callback_query(F.data == "a|imgnew")
async def image_new(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "media"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    await state.set_state(ImgFSM.name)
    await call.answer()
    await call.message.edit_text(
        "➕ <b>افزودن تصویر جدید</b>\n\n"
        "۱) یک <b>اسم یکتا</b> برای عکس بنویسید (لاتین یا فارسی):\n"
        "مثال: treaty_military یا پیمان-نظامی\n برای انصراف /cancel")


@router.message(ImgFSM.name)
async def image_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 60:
        return await message.answer("❌ اسم باید بین ۱ تا ۶۰ حرف باشد.")
    exists = await db.fetchone("SELECT id FROM images WHERE name=?", (name,))
    if exists:
        return await message.answer("❌ این اسم قبلاً استفاده شده — اسم دیگری بنویسید.")
    await state.update_data(img_name=name)
    await state.set_state(ImgFSM.section)
    await message.answer("۲) عکس برای کدام بخش است؟", reply_markup=kb(SECTIONS_ROWS))


@router.callback_query(F.data.startswith("a|imgsec|"))
async def image_section(call: CallbackQuery, state: FSMContext):
    section = call.data.split("|")[2]
    data = await state.get_data()
    if not data.get("img_name"):
        return await call.answer("ابتدا اسم عکس را بفرستید", show_alert=True)
    await state.update_data(img_section=section)
    await state.set_state(ImgFSM.photo)
    await call.answer()
    await call.message.edit_text(
        f"۳) حالا خودِ <b>عکس</b> را بفرستید.\n"
        f"اسم: <code>{data['img_name']}</code> | بخش: {IMAGE_SECTIONS.get(section, section)}\n"
        "برای انصراف /cancel")


@router.message(ImgFSM.photo, F.photo)
async def image_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    file_id = message.photo[-1].file_id
    await db.execute(
        "INSERT INTO images(name, section, file_id, uploaded_by) VALUES(?,?,?,?) "
        "ON CONFLICT(name) DO UPDATE SET section=excluded.section, file_id=excluded.file_id",
        (data["img_name"], data.get("img_section", "general"), file_id, message.from_user.id))
    await log_action(message.from_user.id, "تصاویر",
                     f"{data['img_name']} → {data.get('img_section')}")
    await message.answer(
        f"✅ تصویر «<b>{data['img_name']}</b>» ذخیره شد "
        f"(بخش: {IMAGE_SECTIONS.get(data.get('img_section', 'general'), 'عمومی')}).")
    text, buttons = await image_list_text()
    buttons.append([("➕ افزودن تصویر", "a|imgnew")])
    buttons.append([("◀️ بازگشت", "a|root")])
    await message.answer(text, reply_markup=kb(buttons))


@router.message(ImgFSM.photo)
async def image_photo_invalid(message: Message):
    await message.answer("❌ فقط عکس بفرستید (نه فایل، نه متن).")


@router.callback_query(F.data.startswith("a|imgv|"))
async def image_view(call: CallbackQuery, perms: set):
    if not has(perms, "media"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    img = await db.fetchone("SELECT * FROM images WHERE id=?", (int(call.data.split("|")[2]),))
    if not img:
        return await call.answer("یافت نشد", show_alert=True)
    sec = IMAGE_SECTIONS.get(img["section"], img["section"])
    try:
        await call.message.answer_photo(img["file_id"],
                                        caption=f"🖼 {img['name']} — {sec} <code>#{img['id']}</code>")
    except Exception:
        # نمایش بدون عکس در صورت خطا
        await call.message.answer(f"🖼 {img['name']} — {sec} <code>#{img['id']}</code>\n(پیش‌نمایش ناموفق)")
    buttons = []
    if img["section"] == "flag":
        buttons.append([("🏳 انتساب مستقیم این پرچم به یک کشور", f"a|imgc|{img['id']}|0")])
    buttons.append([("🗑 حذف", f"a|imgdel|{img['id']}")])
    buttons.append([("◀️ بازگشت", "a|img")])
    await call.answer()
    await call.message.answer(
        f"🖼 <b>{img['name']}</b>\nبخش: {sec} | کد: <code>{img['id']}</code>",
        reply_markup=kb(buttons))


@router.callback_query(F.data.startswith("a|imgc|"))
async def image_assign_country_list(call: CallbackQuery, perms: set):
    if not has(perms, "media"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    parts = call.data.split("|")
    img_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    img = await db.fetchone("SELECT * FROM images WHERE id=?", (img_id,))
    if not img:
        return await call.answer("عکس یافت نشد", show_alert=True)
    
    total = (await db.fetchone("SELECT COUNT(*) c FROM countries WHERE is_active=1"))["c"]
    page_size = 8
    countries = await db.fetchall(
        "SELECT id, name, flag FROM countries WHERE is_active=1 ORDER BY name LIMIT ? OFFSET ?",
        (page_size, page * page_size)
    )
    rows = []
    for c in countries:
        rows.append([(f"{c['flag']} {c['name']}", f"a|imgset|{img_id}|{c['id']}")])
    nav = []
    if page > 0:
        nav.append(("‹ قبلی", f"a|imgc|{img_id}|{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(("بعدی ›", f"a|imgc|{img_id}|{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("◀️ بازگشت به عکس", f"a|imgv|{img_id}")])
    await call.answer()
    await call.message.edit_text(
        f"🏳 <b>انتساب پرچم «{img['name']}» به کشور:</b>\n"
        "کشور مورد نظر را انتخاب کنید تا این پرچم برای آن تنظیم شود:",
        reply_markup=kb(rows)
    )


@router.callback_query(F.data.startswith("a|imgset|"))
async def image_assign_country_apply(call: CallbackQuery, perms: set):
    if not has(perms, "media"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    _, _, img_id, cid = call.data.split("|")
    img_id, cid = int(img_id), int(cid)
    img = await db.fetchone("SELECT * FROM images WHERE id=?", (img_id,))
    country = await db.fetchone("SELECT * FROM countries WHERE id=?", (cid,))
    if not img or not country:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("UPDATE countries SET flag_url=? WHERE id=?", (img["file_id"], cid))
    await log_action(call.from_user.id, "تصاویر", f"انتساب پرچم {img['name']} به {country['name']}")
    await call.answer(f"✅ پرچم {country['name']} با موفقیت تنظیم شد!", show_alert=True)
    # بازگشت به صفحه نمایش عکس
    call.data = f"a|imgv|{img_id}"
    await image_view(call, perms)


@router.callback_query(F.data.startswith("a|imgdel|"))
async def image_delete(call: CallbackQuery, perms: set):
    if not has(perms, "media"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    iid = int(call.data.split("|")[2])
    img = await db.fetchone("SELECT * FROM images WHERE id=?", (iid,))
    if not img:
        return await call.answer("یافت نشد", show_alert=True)
    await db.execute("DELETE FROM images WHERE id=?", (iid,))
    await log_action(call.from_user.id, "تصاویر", f"حذف {img['name']}")
    await call.answer("🗑 حذف شد")
    await images_menu(call, perms)
