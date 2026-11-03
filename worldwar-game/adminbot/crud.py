"""موتور CRUD عمومی ربات ادمین.

هر موجودیت رجیسترشده در entities.py به‌طور خودکار این امکانات را می‌گیرد:
مرور با صفحه‌بندی و جستجو، ساخت، ویرایش هر فیلد، حذف — بدون کد اضافه.
همچنین «مرورگر خام دیتابیس» برای جدول‌های رجیسترنشده (۱۰۰٪ همه چیز).
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from adminbot.auth import has
from adminbot.entities import Entity, Field, by_key
from adminbot.tools import log_action
from core.db import db
from core.utils import b36, unb36, fmt

router = Router()
PAGE = 8
LAST_QUERY: dict[tuple[int, str], str] = {}   # آخرین جستجوی هر ادمین برای هر موجودیت
RAW_CACHE: dict[str, str] = {}                # مرورگر خام: کلید t0..n → نام جدول


class CrudFSM(StatesGroup):
    value = State()


def kb(rows: list) -> InlineKeyboardMarkup:
    clean_keyboard: list[list[InlineKeyboardButton]] = []
    for r in rows:
        if not r:
            continue
        if isinstance(r, tuple) and len(r) >= 2 and isinstance(r[0], str):
            clean_keyboard.append([_make_btn(r)])
        elif isinstance(r, (list, tuple)):
            btn_row: list[InlineKeyboardButton] = []
            for item in r:
                if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[0], str):
                    btn_row.append(_make_btn(item))
                elif isinstance(item, InlineKeyboardButton):
                    btn_row.append(item)
            if btn_row:
                clean_keyboard.append(btn_row)
    return InlineKeyboardMarkup(inline_keyboard=clean_keyboard)


def _btn_color(text: str, data: str) -> str:
    """رنگ اینلاین دکمه بر اساس متن/کالبک — Telegram Bot API 7.0."""
    t = (text or "")
    d = (data or "")
    if isinstance(d, str) and (d.startswith("http://") or d.startswith("https://") or d.startswith("tg://")):
        return "white"
    if t.startswith("❌") or any(k in t for k in ("انصراف", "لغو", "حذف", "cancel", "reject", "break")):
        return "red"
    if isinstance(d, str) and (d.startswith("g|cancel") or d.startswith("c|cancel") or
                               d.startswith("a|imgdel") or d.startswith("a|del") or
                               d.startswith("a|reset") or d.startswith("a|rm")):
        return "red"
    if t.startswith("✅") or any(k in t for k in ("تأیید", "تایید", "انتشار", "پذیرفت",
                                                "confirm", "continue", "ادامه")):
        return "green"
    if "◀️" in t or "بازگشت" in t or t.startswith("🏠") or d in ("g|emp", "g|main", "g|home"):
        return "white"
    return "blue"


def _make_btn(item: tuple) -> InlineKeyboardButton:
    text = item[0]
    data = item[1]
    if len(item) >= 3 and item[2] == "url":
        return InlineKeyboardButton(text=text, url=data)
    if isinstance(data, str) and (data.startswith("http://") or data.startswith("https://") or data.startswith("tg://")):
        return InlineKeyboardButton(text=text, url=data)
    return InlineKeyboardButton(text=text, callback_data=str(data),
                                color=_btn_color(text, data))


def cd(*parts) -> str:
    return "c|" + "|".join(str(p) for p in parts)


# ─── مرورگر خام دیتابیس ───


async def raw_tables() -> dict[str, str]:
    if not RAW_CACHE:
        rows = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        for i, r in enumerate(rows):
            RAW_CACHE[f"t{i}"] = r["name"]
    return RAW_CACHE


async def raw_entity(key: str) -> Entity | None:
    tables = await raw_tables()
    table = tables.get(key)
    if not table:
        return None
    cols = await db.fetchall(f"PRAGMA table_info({table})")
    col_names = [c["name"] for c in cols]
    pk = "id" if "id" in col_names else "rowid"
    fields: list[Field] = []
    title_expr = None
    search_cols: list[str] = []
    json_cols = {"options", "effects", "perms", "chosen_laws", "religion_effects",
                 "government_effects", "trade_banned"}
    bool_names = {"banned", "announced", "success", "permission", "war_crime", "has_sea",
                  "is_special", "is_active", "is_super"}
    title_pref = ("name", "title", "key", "username", "action", "kind", "status", "text")
    for c in cols:
        name, ctype = c["name"], (c["type"] or "TEXT").upper()
        ftype = "text"
        if "INT" in ctype:
            ftype = "int"
        elif "REAL" in ctype or "FLOA" in ctype or "DOUB" in ctype:
            ftype = "float"
        if name in json_cols:
            ftype = "json"
        elif name in bool_names:
            ftype = "bool"
        skip = (name == pk) or name.endswith("_at") or name.endswith("_file_id")
        fields.append(Field(name, name, ftype, skip_in_new=skip))
        if title_expr is None and name in title_pref:
            title_expr = name
        if name in title_pref or name in ("full_name", "region"):
            search_cols.append(name)
    if title_expr is None:
        title_expr = f"'#' || {pk}"
    return Entity(key, table, f"🗄 {table}", "🗄", "logs", fields,
                  list_title=title_expr, pk=pk, order_by=f"{pk} DESC",
                  search_cols=search_cols or [pk])


async def resolve_entity(key: str) -> Entity | None:
    if key.startswith("t") and key[1:].isdigit():
        return await raw_entity(key)
    return by_key(key)


# ─── نمایش مقادیر ───


async def display_value(f: Field, value) -> str:
    if value is None or value == "":
        return "<i>—</i>"
    if f.type == "bool":
        return "✅" if value else "❌"
    if f.type == "ref":
        try:
            ref = await db.fetchone(
                f"SELECT {f.ref_title} AS t FROM {f.ref_table} WHERE id=?", (int(value),))
            return f"{ref['t']} <code>({value})</code>" if ref else f"<code>{value}</code> (حذف‌شده)"
        except Exception:
            return str(value)
    if f.type == "json":
        s = str(value)
        return f"<code>{s[:120]}</code>" + ("…" if len(s) > 120 else "")
    if f.type == "int":
        return fmt(value)
    return str(value)[:150]


# ─── مرور (Browse) ───


async def browse_text_kb(entity: Entity, page: int, query: str):
    where, params = "1=1", []
    if query:
        like = f"%{query}%"
        conds = []
        for col in (entity.search_cols or [entity.pk]):
            conds.append(f"CAST({col} AS TEXT) LIKE ?")
            params.append(like)
        where = "(" + " OR ".join(conds) + ")"
    total = (await db.fetchone(
        f"SELECT COUNT(*) AS c FROM {entity.table} WHERE {where}", tuple(params)))["c"]
    rows = await db.fetchall(
        f"SELECT {entity.pk} AS rid, {entity.list_title} AS t" +
        (f", {entity.list_sub} AS s" if entity.list_sub else "") +
        f" FROM {entity.table} WHERE {where} ORDER BY {entity.order_by} LIMIT ? OFFSET ?",
        tuple(params) + (PAGE, page * PAGE))
    pages = max(1, (total + PAGE - 1) // PAGE)
    lines = [
        f"{entity.icon} <b>{entity.title}</b>",
        f"تعداد کل: <b>{fmt(total)}</b>" + (f" | 🔍 «{query}»" if query else ""),
        f"صفحه {page + 1} از {pages}\n",
    ]
    buttons = []
    for r in rows:
        if entity.list_sub and r.get("s"):
            lines.append(f"• {r['t']} <code>#{r['rid']}</code>\n   <i>{r['s']}</i>")
        else:
            lines.append(f"• {r['t']} <code>#{r['rid']}</code>")
        buttons.append([(str(r["t"])[:60], cd(entity.key, "r", r["rid"]))])
    if not rows:
        lines.append("<i>— خالی —</i>")
    nav = []
    if page > 0:
        nav.append(("‹ قبلی", cd(entity.key, "p", page - 1)))
    if (page + 1) * PAGE < total:
        nav.append(("بعدی ›", cd(entity.key, "p", page + 1)))
    if nav:
        buttons.append(nav)
    buttons.append([("🔍 جستجو", cd(entity.key, "s"))])
    if entity.can_create:
        buttons.append([("➕ افزودن", cd(entity.key, "n"))])
    if entity.key.startswith("t"):
        buttons.append([("◀️ جداول", "a|db")])
    else:
        buttons.append([("◀️ بازگشت", f"a|grp|{entity.perm}")])
    return "\n".join(lines), kb(buttons)


# ─── مسیریابی CRUD ───


@router.callback_query(F.data.startswith("c|"))
async def crud_router(call: CallbackQuery, state: FSMContext, perms: set):
    parts = call.data.split("|")
    if len(parts) < 3:
        return await call.answer("درخواست نامعتبر", show_alert=True)
    ek = parts[1]
    entity = await resolve_entity(ek)
    if not entity:
        return await call.answer("موجودیت یافت نشد", show_alert=True)
    if not entity.key.startswith("t") and not has(perms, entity.perm):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    action = parts[2]
    arg = parts[3] if len(parts) > 3 else "0"
    arg2 = parts[4] if len(parts) > 4 else "0"
    arg3 = parts[5] if len(parts) > 5 else ""

    if action == "p":
        page = max(0, int(arg) if arg.lstrip("-").isdigit() else 0)
        query = LAST_QUERY.get((call.from_user.id, ek), "")
        text, markup = await browse_text_kb(entity, page, query)
        await call.answer()
        return await call.message.edit_text(text, reply_markup=markup)
    if action == "s":
        await state.set_state(CrudFSM.value)
        await state.update_data(crud_mode="search", crud_ek=ek)
        await call.answer()
        return await call.message.edit_text(
            f"🔍 <b>جستجو در {entity.title}</b>\n\nعبارت جستجو را بفرستید:\n برای انصراف /cancel")
    if action == "r":
        return await row_view(call, entity, arg)
    if action == "f":
        return await field_view(call, state, entity, arg, arg2)
    if action == "v":
        return await set_value_direct(call, entity, arg, arg2, arg3)
    if action == "o":
        return await ref_picker(call, entity, arg, arg2, int(arg3) if arg3.isdigit() else 0)
    if action == "t":
        return await toggle_bool(call, entity, arg, arg2)
    if action == "d":
        return await delete_confirm(call, entity, arg)
    if action == "D":
        return await delete_execute(call, entity, arg)
    if action == "n":
        return await new_start(call, state, entity)
    if action == "ns":
        return await new_skip(call, state, entity)
    await call.answer("?", show_alert=True)


# ─── نمای ردیف ───


async def get_row(entity: Entity, rid) -> dict | None:
    try:
        if entity.pk == "rowid":
            return await db.fetchone(
                f"SELECT *, rowid FROM {entity.table} WHERE rowid=?", (rid,))
        return await db.fetchone(f"SELECT * FROM {entity.table} WHERE {entity.pk}=?", (rid,))
    except Exception:
        return None


async def row_view(call: CallbackQuery, entity: Entity, rid, toast: str = ""):
    row = await get_row(entity, rid)
    if not row:
        return await call.answer("ردیف یافت نشد", show_alert=True)
    lines = [f"{entity.icon} <b>{entity.title}</b> — ردیف #{row.get(entity.pk, rid)}\n"]
    for f in entity.fields:
        val = await display_value(f, row.get(f.key))
        lines.append(f"▪️ <b>{f.label}:</b> {val}")
    if entity.note:
        lines.append(f"\n💡 {entity.note}")
    buttons = []
    edit_pairs = [(f"✏️ {f.label}"[:30], cd(entity.key, "f", row.get(entity.pk), i))
                  for i, f in enumerate(entity.fields)]
    for i in range(0, len(edit_pairs), 2):
        buttons.append(edit_pairs[i:i + 2])
    if entity.can_delete:
        buttons.append([("🗑 حذف", cd(entity.key, "d", row.get(entity.pk)))])
    if entity.key.startswith("t"):
        buttons.append([("◀️ جداول", "a|db")])
    else:
        buttons.append([("◀️ لیست", cd(entity.key, "p", 0))])
    if toast:
        await call.answer(toast)
    try:
        await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))
    except Exception:
        pass


# ─── ویرایش فیلد ───


async def field_view(call: CallbackQuery, state: FSMContext, entity: Entity, rid, fi_s: str):
    fi = int(fi_s) if fi_s.isdigit() else 0
    if fi >= len(entity.fields):
        return await call.answer("فیلد یافت نشد", show_alert=True)
    f = entity.fields[fi]
    row = await get_row(entity, rid)
    if not row:
        return await call.answer("ردیف یافت نشد", show_alert=True)
    current = await display_value(f, row.get(f.key))
    lines = [f"✏️ <b>ویرایش «{f.label}»</b>\n", f"مقدار فعلی: {current}"]
    if f.help:
        lines.append(f"\n💡 {f.help}")
    buttons = []
    if f.type == "bool":
        target = "❌" if row.get(f.key) else "✅"
        buttons.append([(f"تغییر به {target}", cd(entity.key, "t", rid, fi))])
    elif f.type == "enum":
        lines.append("\nگزینه جدید را انتخاب کنید:")
        for i, opt in enumerate(f.options):
            cur = " ✔" if str(row.get(f.key)) == str(opt) else ""
            buttons.append([(f"{opt}{cur}", cd(entity.key, "v", rid, fi, b36(i)))])
    elif f.type == "ref":
        lines.append("\nمقدار جدید را از لیست انتخاب کنید:")
        return await ref_picker(call, entity, rid, fi, 0)
    else:
        await state.set_state(CrudFSM.value)
        await state.update_data(crud_mode="edit", crud_ek=entity.key, crud_rid=rid, crud_fi=fi)
        lines.append("\n✍️ مقدار جدید را بفرستید:\n برای انصراف /cancel")
    buttons.append([("◀️ بازگشت", cd(entity.key, "r", rid))])
    await call.answer()
    await call.message.edit_text("\n".join(lines), reply_markup=kb(buttons))


async def ref_picker(call: CallbackQuery, entity: Entity, rid, fi_s: str, page: int):
    fi = int(fi_s) if fi_s.isdigit() else 0
    f = entity.fields[fi]
    rows = await db.fetchall(
        f"SELECT id, {f.ref_title} AS t FROM {f.ref_table} ORDER BY id LIMIT ? OFFSET ?",
        (PAGE, page * PAGE))
    total = (await db.fetchone(f"SELECT COUNT(*) AS c FROM {f.ref_table}"))["c"]
    buttons = []
    for r in rows:
        buttons.append([(f"✅ {r['t']} ({r['id']})", cd(entity.key, "v", rid, fi, b36(r["id"])))])
    nav = []
    if page > 0:
        nav.append(("‹ قبلی", cd(entity.key, "o", rid, fi, page - 1)))
    if (page + 1) * PAGE < total:
        nav.append(("بعدی ›", cd(entity.key, "o", rid, fi, page + 1)))
    if nav:
        buttons.append(nav)
    buttons.append([("∅ خالی", cd(entity.key, "v", rid, fi, "n"))])
    buttons.append([("◀️ بازگشت", cd(entity.key, "r", rid))])
    await call.answer()
    await call.message.edit_text(
        f"🔗 انتخاب <b>{f.label}</b> — صفحه {page + 1} (مجموع {fmt(total)}):",
        reply_markup=kb(buttons))


async def set_value_direct(call: CallbackQuery, entity: Entity, rid, fi_s: str, val: str):
    fi = int(fi_s) if fi_s.isdigit() else 0
    f = entity.fields[fi]
    if val == "n":
        value = None
    elif f.type == "enum":
        idx = unb36(val)
        value = f.options[idx] if 0 <= idx < len(f.options) else None
    elif f.type == "ref":
        value = unb36(val) or None
    else:
        value = val
    await db.execute(f"UPDATE {entity.table} SET {f.key}=? WHERE {entity.pk}=?", (value, rid))
    await log_action(call.from_user.id, "ویرایش", f"{entity.table}#{rid} → {f.key} = {value}")
    await row_view(call, entity, rid, toast="✅ ذخیره شد")


async def toggle_bool(call: CallbackQuery, entity: Entity, rid, fi_s: str):
    fi = int(fi_s) if fi_s.isdigit() else 0
    f = entity.fields[fi]
    row = await get_row(entity, rid)
    if not row:
        return await call.answer("ردیف یافت نشد", show_alert=True)
    new = 0 if row.get(f.key) else 1
    await db.execute(f"UPDATE {entity.table} SET {f.key}=? WHERE {entity.pk}=?", (new, rid))
    await log_action(call.from_user.id, "ویرایش", f"{entity.table}#{rid} → {f.key} = {new}")
    await row_view(call, entity, rid, toast="✅ تغییر کرد")


# ─── ورودی متنی (ویرایش/جستجو/ساخت) ───


@router.message(CrudFSM.value)
async def crud_input(message: Message, state: FSMContext, perms: set):
    data = await state.get_data()
    mode = data.get("crud_mode")
    ek = data.get("crud_ek")
    entity = await resolve_entity(ek) if ek else None
    if not mode or not entity:
        await state.clear()
        return await message.answer("❌ حالت نامعتبر — از /panel شروع کنید.")
    text = (message.text or "").strip()

    if mode == "search":
        await state.clear()
        LAST_QUERY[(message.from_user.id, ek)] = text
        text_out, markup = await browse_text_kb(entity, 0, text)
        return await message.answer(text_out, reply_markup=markup)

    if mode == "edit":
        fi = int(data.get("crud_fi", 0))
        f = entity.fields[fi]
        value, err = parse_value(f, text)
        if err:
            return await message.answer(f"❌ {err}")
        rid = data.get("crud_rid")
        await db.execute(f"UPDATE {entity.table} SET {f.key}=? WHERE {entity.pk}=?", (value, rid))
        await log_action(message.from_user.id, "ویرایش", f"{entity.table}#{rid} → {f.key} = {value}")
        await state.clear()
        await message.answer("✅ ذخیره شد.")
        fake = _FakeCall(message)
        await row_view(fake, entity, rid)
        return

    if mode == "new":
        fi = int(data.get("crud_fi", 0))
        f = entity.fields[fi]
        value, err = parse_value(f, text)
        if err:
            return await message.answer(f"❌ {err}")
        new_data = data.get("new_data", {})
        new_data[f.key] = value
        await state.update_data(new_data=new_data, crud_fi=fi + 1)
        return await new_next(message, state, entity, new_data)


class _FakeCall:
    """شیء شبیه CallbackQuery برای بازتولید نما بعد از ورودی متنی."""

    def __init__(self, message: Message):
        self.message = message
        self.from_user = message.from_user
        self.bot = message.bot

    async def answer(self, text: str = "", *a, **k):
        pass


def parse_value(f: Field, text: str):
    """اعتبارسنجی ورودی بر اساس نوع فیلد؛ (value, error)."""
    if f.type == "int":
        try:
            v = int(text.replace(",", "").strip())
        except ValueError:
            return None, "لطفاً فقط عدد صحیح بفرستید"
        if f.min is not None and v < f.min:
            return None, f"عدد باید ≥ {fmt(f.min)} باشد"
        if f.max is not None and v > f.max:
            return None, f"عدد باید ≤ {fmt(f.max)} باشد"
        return v, None
    if f.type == "float":
        try:
            v = float(text.replace(",", "").strip())
        except ValueError:
            return None, "لطفاً عدد بفرستید"
        if f.min is not None and v < f.min:
            return None, f"عدد باید ≥ {f.min} باشد"
        if f.max is not None and v > f.max:
            return None, f"عدد باید ≤ {f.max} باشد"
        return v, None
    if f.type == "bool":
        if text in ("1", "true", "بله", "✅"):
            return 1, None
        if text in ("0", "false", "خیر", "❌"):
            return 0, None
        return None, "فقط 0 یا 1 بفرستید"
    if f.type == "json":
        import json
        s = text.strip()
        if s in ("", "{}", "[]"):
            return s, None
        try:
            json.loads(s)
            return s, None
        except ValueError:
            return None, 'JSON نامعتبر است — مثل ["a","b"] یا {"key":1}'
    if f.type == "ref":
        try:
            return int(text.strip()), None
        except ValueError:
            return None, "آیدی عددی بفرستید"
    if f.required and not text:
        return None, "این فیلد اجباری است"
    return text, None


# ─── ساخت ردیف جدید ───


async def new_start(call: CallbackQuery, state: FSMContext, entity: Entity):
    if not entity.can_create:
        return await call.answer("ساخت دستی مجاز نیست", show_alert=True)
    await state.set_state(CrudFSM.value)
    await state.update_data(crud_mode="new", crud_ek=entity.key, crud_fi=0, new_data={})
    f = entity.fields[0]
    body = f"➕ <b>ساخت جدید در «{entity.title}»</b>\n\n" \
           f"۱) <b>{f.label}</b>" + (" 🔹" if f.required else " (اختیاری)")
    if f.help:
        body += f"\n💡 {f.help}"
    await call.answer()
    await call.message.edit_text(body + "\n\nمقدار را بفرستید:", reply_markup=new_kb(entity))


def new_kb(entity: Entity) -> InlineKeyboardMarkup:
    return kb([
        [("⏭ رد کردن این فیلد", cd(entity.key, "ns"))],
        [("❌ انصراف", cd(entity.key, "p", 0))],
    ])


async def new_skip(call: CallbackQuery, state: FSMContext, entity: Entity):
    data = await state.get_data()
    if data.get("crud_mode") != "new" or data.get("crud_ek") != entity.key:
        return await call.answer("حالت ساخت فعال نیست", show_alert=True)
    fi = int(data.get("crud_fi", 0))
    if fi < len(entity.fields) and entity.fields[fi].required:
        return await call.answer("این فیلد اجباری است!", show_alert=True)
    await state.update_data(crud_fi=fi + 1)
    await call.answer()
    await new_next(call.message, state, entity, data.get("new_data", {}))


async def new_next(message: Message, state: FSMContext, entity: Entity, new_data: dict):
    data = await state.get_data()
    fi = int(data.get("crud_fi", 0))
    if fi >= len(entity.fields):
        await state.clear()
        cols, marks, vals = [], [], []
        for f in entity.fields:
            if new_data.get(f.key) is not None:
                cols.append(f.key)
                marks.append("?")
                vals.append(new_data[f.key])
        if not cols:
            return await message.answer("❌ هیچ فیلدی پر نشده بود.")
        rid = await db.execute(
            f"INSERT INTO {entity.table}({','.join(cols)}) VALUES({','.join(marks)})",
            tuple(vals))
        await log_action(message.from_user.id, "ساخت", f"{entity.table}#{rid} ← {new_data}")
        await message.answer(f"✅ ردیف #{rid} در «{entity.title}» ساخته شد!")
        await row_view(_FakeCall(message), entity, rid)
        return
    f = entity.fields[fi]
    done = [f"✅ {ff.label}: {await display_value(ff, new_data.get(ff.key))}"
            for ff in entity.fields[:fi] if ff.key in new_data]
    body = f"➕ <b>ساخت جدید — {entity.title}</b>\n\n"
    if done:
        body += "\n".join(done) + "\n\n"
    body += f"{fi + 1}) <b>{f.label}</b>" + (" 🔹" if f.required else " (اختیاری)")
    if f.help:
        body += f"\n💡 {f.help}"
    await message.answer(body + "\n\nمقدار را بفرستید:", reply_markup=new_kb(entity))


# ─── حذف ───


async def delete_confirm(call: CallbackQuery, entity: Entity, rid):
    row = await get_row(entity, rid)
    if not row:
        return await call.answer("ردیف یافت نشد", show_alert=True)
    await call.answer()
    await call.message.edit_text(
        f"🗑 <b>حذف ردیف #{rid} از «{entity.title}»</b>\n\n"
        "⚠️ این عمل غیرقابل بازگشت است و ممکن است داده‌های وابسته را تحت تأثیر قرار دهد.\nحذف می‌کنید؟",
        reply_markup=kb([
            [("🗑 بله، حذف کن", cd(entity.key, "D", rid))],
            [("◀️ انصراف", cd(entity.key, "r", rid))],
        ]))


async def delete_execute(call: CallbackQuery, entity: Entity, rid):
    await db.execute(f"DELETE FROM {entity.table} WHERE {entity.pk}=?", (rid,))
    await log_action(call.from_user.id, "حذف", f"{entity.table}#{rid}")
    await call.answer("🗑 حذف شد")
    text, markup = await browse_text_kb(entity, 0, LAST_QUERY.get((call.from_user.id, entity.key), ""))
    await call.message.edit_text(text, reply_markup=markup)


@router.message(Command("cancel"))
async def crud_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ عملیات لغو شد. برای بازگشت /panel را بزنید.")
