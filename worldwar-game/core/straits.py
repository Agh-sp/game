"""تنگه‌های راهبردی — نبرد دریایی واقعی، تصاحب، عوارض ۱.۵٪ درآمد غیرمالیاتی."""
import random

from core.db import db, get_setting
from core.economy import get_country
from core.events import log_event
from core.images import announce_img
from core.utils import fmt, iso


async def naval_power(user_id: int) -> int:
    """قدرت دریایی = توان تجهیزات دریایی (ناو/زیردریایی/قایق/...) + پایگاه‌های دریایی."""
    rows = await db.fetchall(
        "SELECT a.quantity, (e.attack_power + e.defense_power) AS power FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id "
        "JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND c.key='sea'", (user_id,))
    total = int(sum(r["quantity"] * (r["power"] or 0) for r in rows))
    return total + await naval_base_power(user_id)


async def my_straits(user_id: int) -> list[dict]:
    return await db.fetchall("SELECT * FROM straits WHERE owner_id=? ORDER BY id", (user_id,))


async def coastal_defense(user_id: int) -> int:
    """توان پدافند ساحلی: ۲۵٪ قدرت دفاعی تجهیزات زمینی/هوایی/پدافندی مدافع."""
    rows = await db.fetchall(
        "SELECT a.quantity, e.defense_power AS def, c.key AS cat_key, e.subcategory AS sub FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id LEFT JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment'", (user_id,))
    total = 0.0
    for r in rows:
        sub = (r["sub"] or "").lower()
        if r["cat_key"] in ("land", "air") or sub in ("air_defense", "patriot", "coastal"):
            total += (r["def"] or 0) * (r["quantity"] or 0)
    return int(total * 0.25)


async def fleet_composition(user_id: int) -> dict:
    """ترکیب واقعی ناوگان برای انتخاب استراتژی (زیردریایی/ناو/هواپیمابر/سرباز)."""
    rows = await db.fetchall(
        "SELECT a.quantity, e.subcategory AS sub, e.name AS name FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND c.key='sea' AND a.quantity>0", (user_id,))
    comp = {"submarine": 0, "carrier": 0, "surface": 0}
    for r in rows:
        sub = (r["sub"] or "").lower()
        name = r["name"] or ""
        qty = int(r["quantity"] or 0)
        if sub == "submarine" or "زیردریایی" in name:
            comp["submarine"] += qty
        elif sub == "carrier" or "ناو هواپیمابر" in name:
            comp["carrier"] += qty
            comp["surface"] += qty
        else:
            comp["surface"] += qty
    soldiers = await db.fetchone(
        "SELECT COALESCE(SUM(quantity),0) c FROM player_assets WHERE user_id=? AND item_type='soldier'",
        (user_id,))
    if soldiers and soldiers["c"]:
        comp["soldier"] = int(soldiers["c"])
        comp["air"] = comp.get("carrier", 0)
    return comp


async def naval_defense(of_user: int) -> int:
    """توان دفاع دریایی مالک تنگه: ناوگان + پدافند ساحلی."""
    return await naval_power(of_user) + await coastal_defense(of_user)


async def naval_base_power(user_id: int) -> int:
    """🚢 قدرت اضافی از پایگاه‌های دریایی فعال (اجارهٔ بندر کشورهای ساحلی).

    کشورهای بدون مرز دریایی با ساخت پایگاه دریایی می‌توانند ناوگان خود را در
    بندر کشور میزبان مستقر کنند و در عملیات دریایی/تنگه‌ها شرکت کنند.
    """
    try:
        rows = await db.fetchall(
            "SELECT COUNT(*) c FROM bases WHERE guest_id=? AND status='active' "
            "AND COALESCE(kind,'land')='naval'", (user_id,))
        count = int((rows[0] if rows else {}).get("c") or 0)
    except Exception:
        return 0
    if count <= 0:
        return 0
    per = int(float(await get_setting("naval_base_sea_power", "1500")))
    return count * per


async def has_sea_access(user_id: int) -> tuple[bool, str]:
    """آیا این کشور دسترسی دریایی دارد؟ (مرز دریایی یا پایگاه دریایی فعال)"""
    country = await get_country(user_id)
    if country and country.get("has_sea"):
        return True, "مرز دریایی"
    if await naval_base_power(user_id) > 0:
        return True, "پایگاه دریایی"
    return False, ""


async def capture_requirements(user_id: int, strait: dict) -> tuple[bool, str]:
    """آیا این کشور می‌تواند وارد نبرد تنگه شود؟ (نتیجهٔ نبرد در capture_strait است)"""
    country = await get_country(user_id)
    if not country:
        return False, "❌ شما کشوری ندارید!"
    ok_sea, how = await has_sea_access(user_id)
    if not ok_sea:
        return False, ("❌ کشور شما مرز دریایی ندارد!\n"
                       "🚢 می‌توانید یک <b>پایگاه دریایی</b> در کشور ساحلی بسازید "
                       "(🪖 ارتش ← 🚚 پایگاه دریایی) تا در عملیات دریایی شرکت کنید.")
    my = await naval_power(user_id)
    min_naval = int(float(await get_setting("strait_min_naval", "500")))
    if my < min_naval:
        return False, (f"❌ برای عملیات دریایی حداقل {fmt(min_naval)} قدرت دریایی لازم است "
                       f"(شما: {fmt(my)}). از 🎖 پادگان ناو/زیردریایی بخرید یا "
                       "🚢 پایگاه دریایی بسازید.")
    if not strait["owner_id"]:
        return True, ""
    if strait["owner_id"] == user_id:
        return False, "شما مالک این تنگه هستید."
    # ⚔️ حمله هرگز بلاک نمی‌شود: نبرد «فرسایشی» است و هر حمله بخشی از
    # ناوگان مدافع را از بین می‌برد، حتی اگر این بار تنگه تصرف نشود.
    return True, ""


async def attack_outlook(user_id: int, strait: dict) -> dict:
    """پیش‌بینی حملهٔ فرسایشی برای نمایش به بازیکن (هیچ‌چیز را تغییر نمی‌دهد).

    خروجی:
        my_naval     قدرت دریایی مهاجم
        owner_def    توان دفاع دریایی مدافع
        need         قدرت لازم برای تصرف در همین حمله
        win_chance   درصد شانس تصرف در این حمله
        can_capture  آیا این حمله شانس تصرف دارد؟
        attrition    درصدی از ناوگان مدافع که در هر حمله فرسوده می‌شود
        needed_rounds  چند حملهٔ مشابه لازم است تا مدافع فرسوده شود
        owner_country
    """
    from core import combat

    my_naval = await naval_power(user_id)
    owner_id = strait["owner_id"]
    owner_def = await naval_defense(owner_id) if owner_id else 0
    ratio = float(await get_setting("strait_capture_ratio", "1.3"))
    need = int(owner_def * ratio)
    comp = await fleet_composition(user_id)
    strat = combat.pick_strategy("sea", comp, defender_has_navy=await _def_has_navy(owner_id))
    atk_power = my_naval * strat["atk"]
    def_power = owner_def * strat["def"]
    chance = combat.battle_chance(atk_power, def_power) if def_power > 0 else 1.0
    attrition = float(await get_setting("strait_attrition_percent", "18")) / 100
    owner_country = await get_country(owner_id) if owner_id else None

    # چند حمله لازم است تا دفاع مدافع به سطحی برسد که قابل شکستن شود
    rounds = 0
    remaining = owner_def
    while remaining > 0 and atk_power > 0 and rounds < 30:
        if atk_power >= remaining * ratio:
            break
        remaining = int(remaining * (1 - attrition))
        rounds += 1
    return {
        "my_naval": my_naval, "owner_def": owner_def, "need": need,
        "win_chance": round(chance * 100, 1), "can_capture": atk_power >= need,
        "attrition": round(attrition * 100, 1), "needed_rounds": rounds,
        "owner_country": owner_country, "strategy": strat,
        "atk_power": int(atk_power), "def_power": int(def_power),
    }


async def _def_has_navy(owner_id: int | None) -> bool:
    if not owner_id:
        return False
    return await naval_power(owner_id) > 0


async def capture_strait(bot, user_id: int, strait_id: int) -> str:
    """نبرد دریایی واقعی برای تسخیر تنگه.

    توان ناوگان دو طرف از تجهیزات واقعی محاسبه می‌شود، استراتژی حمله از ترکیب
    ناوگان انتخاب می‌گردد، نتیجه بر اساس نسبت توان تعیین می‌شود و **هر دو طرف**
    تلفات واقعی می‌دهند. گزارش کامل (استراتژی + خسارات دو طرف) در کانال اعلام می‌شود.
    """
    from core import combat

    s = await db.fetchone("SELECT * FROM straits WHERE id=? AND is_active=1", (strait_id,))
    if not s:
        return "تنگه یافت نشد."
    ok, err = await capture_requirements(user_id, s)
    if not ok:
        return err
    old_owner = s["owner_id"]
    old_country = await get_country(old_owner) if old_owner else None
    me = await get_country(user_id)

    my_naval = await naval_power(user_id)
    comp = await fleet_composition(user_id)

    # ─── تنگهٔ بدون مالک: استقرار ناوگان بدون درگیری ───
    if not old_owner or old_owner == user_id:
        strat = combat.strategy("garrison")
        atk_losses, atk_units = await combat.apply_unit_losses(user_id, strat["atk_loss"], ("sea",))
        await db.execute("UPDATE straits SET owner_id=?, captured_at=? WHERE id=?",
                         (user_id, iso(), strait_id))
        await log_event("strait", f"{me['name']} تنگه {s['name']} را بدون درگیری تصاحب کرد")
        text = combat.battle_report(
            strat=strat, atk_country=me, def_country=old_country or me,
            atk_power=my_naval, def_power=0, chance=0.99, won=True,
            atk_losses=atk_losses, def_losses=[], atk_units=atk_units, def_units=0,
            atk_ratio=strat["atk_loss"], def_ratio=0.0,
            title=f"تصاحب {s['name']}")
        text += (f"\n\n⚓ کنترل آبراه <b>{s['name']}</b> به {me['flag']} <b>{me['name']}</b> منتقل شد.\n"
                 "💰 ۱.۵٪ عوارض ترانزیت درآمد غیرمالیاتی کشورهای دارای مرز دریایی به شما می‌رسد.")
        await announce_img(bot, text, "strait")
        return (f"✅ {s['name']} بدون درگیری تصرف شد!\n"
                "۱.۵٪ عوارض ترانزیت جهانی به حساب شما واریز می‌شود."
                + ("\n💥 تلفات استقرار: " + " ، ".join(atk_losses[:3]) if atk_losses else ""))

    # ─── نبرد دریایی واقعی با مالک ───
    def_rows = await combat.equipment_rows(old_owner, ("sea",))
    def_naval = await naval_power(old_owner)
    def_coast = await coastal_defense(old_owner)
    strat = combat.pick_strategy("sea", comp, defender_has_navy=def_naval > 0)

    atk_power = my_naval * strat["atk"]
    def_power = (def_naval + def_coast) * strat["def"]
    chance = combat.battle_chance(atk_power, def_power)
    won = random.random() < chance
    atk_ratio, def_ratio = combat.loss_ratios(chance, strat)

    # ⚔️ فرسایش تضمینی: حتی اگر حمله دفع شود، ناوگان مدافع آسیب می‌بیند.
    # هر حمله دست‌کم `strait_attrition_percent` درصد از ناوگانش را از دست می‌دهد.
    attrition = float(await get_setting("strait_attrition_percent", "18")) / 100
    min_atk_loss = float(await get_setting("strait_attrition_min_attacker", "5")) / 100
    def_ratio = max(def_ratio, attrition)
    atk_ratio = max(atk_ratio, min_atk_loss)

    # تلفات واقعی هر دو طرف (کسر از ناوگان و سربازان)
    # 🎯 همان باگ «۵ کشتی، ۱۰۰ ناو نابود» در نبرد تنگه هم بود: تلفات درصدی از کل
    # ناوگان گرفته می‌شد. اکنون سقف تلفات مدافع به اندازهٔ ناوگان واقعاً درگیر
    # مهاجم است و تجهیزات غیردریایی هم آسیب نمی‌بینند.
    atk_rows = await combat.equipment_rows(user_id, ("sea",))
    atk_units_in_fight = sum(int(r.get("quantity") or 0) for r in atk_rows)
    def_kill_cap = await combat.defend_cap(user_id, atk_units_in_fight)
    atk_losses, atk_units = await combat.apply_capped_losses(
        user_id, atk_rows, atk_ratio, atk_units_in_fight, "equipment")
    def_losses, def_units = await combat.apply_front_losses(
        old_owner, def_rows, def_ratio, def_kill_cap, "equipment", ("sea", "air"))
    if strat["key"] in ("amphibious", "combined"):
        s_atk, s_atk_u = await combat.apply_soldier_losses(user_id, atk_ratio * 0.6)
        if s_atk:
            atk_losses += s_atk
            atk_units += s_atk_u
    s_def, s_def_u = await combat.apply_soldier_losses(old_owner, def_ratio * 0.5)
    if s_def:
        def_losses += s_def
        def_units += s_def_u

    extra = [
        f"♻️ <b>نبرد فرسایشی:</b> ناوگان مدافع {round(attrition * 100)}٪ آسیب دید.",
        f"⚓ <b>ناوگان درگیر:</b> شما {fmt(atk_units_in_fight)} یگان — "
        f"سقف انهدام ناوگان مدافع در این نبرد: {fmt(def_kill_cap)} یگان",
    ]
    if won:
        await db.execute("UPDATE straits SET owner_id=?, captured_at=? WHERE id=?",
                         (user_id, iso(), strait_id))
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-5) WHERE user_id=?",
                         (old_owner,))
        extra.append("🚩 تنگه از کنترل مدافع خارج شد (-۵٪ رضایت ملی مدافع).")
        await log_event("strait", f"{me['name']} در نبرد دریایی تنگه {s['name']} را از "
                                  f"{old_country['name'] if old_country else 'مالک'} گرفت")
    else:
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-3) WHERE user_id=?",
                         (user_id,))
        await db.execute("UPDATE states SET satisfaction=MIN(100, satisfaction+3) WHERE user_id=?",
                         (old_owner,))
        extra.append("🏳 مالکیت تنگه تغییر نکرد؛ مدافع مواضع خود را حفظ کرد (+۳٪ رضایت مدافع).")
        await log_event("strait", f"حمله دریایی {me['name']} به {s['name']} دفع شد")

    report = combat.battle_report(
        strat=strat, atk_country=me, def_country=old_country,
        atk_power=atk_power, def_power=def_power, chance=chance, won=won,
        atk_losses=atk_losses, def_losses=def_losses,
        atk_units=atk_units, def_units=def_units,
        atk_ratio=atk_ratio, def_ratio=def_ratio,
        extra_lines=extra, title=f"نبرد دریایی {s['name']}")
    await announce_img(bot, report, "strait")

    # اطلاع به مدافع
    try:
        await bot.send_message(old_owner, report)
    except Exception:
        pass

    if won:
        head = (f"✅ <b>{s['name']} تسخیر شد!</b>\n"
                f"🧠 استراتژی پیروز: {strat['emoji']} {strat['name']}\n"
                "💰 ۱.۵٪ عوارض ترانزیت به خزانه شما واریز می‌شود.")
    else:
        old_def = def_naval + def_coast
        new_def = await naval_defense(old_owner) if old_owner else 0
        head = (f"❌ <b>حمله به {s['name']} دفع شد!</b>\n"
                f"🧠 استراتژی: {strat['emoji']} {strat['name']} — ناوگان مدافع مقاومت کرد.\n"
                "مالکیت تنگه تغییر نکرد.\n"
                f"♻️ <b>نبرد فرسایشی — اما حمله بی‌اثر نبود:</b> دفاع مدافع از "
                f"<b>{fmt(old_def)}</b> به <b>{fmt(new_def)}</b> کاهش یافت "
                f"(−{fmt(max(0, old_def - new_def))}).\n"
                "🔁 با حمله‌های پشت‌سرهم می‌توانید ناوگان او را فرسوده و بار بعد تصرف کنید.")
    if atk_losses:
        head += f"\n💥 تلفات ناوگان شما ({round(atk_ratio * 100)}%): " + " ، ".join(atk_losses[:4])
    else:
        head += "\n💥 ناوگان شما تلفاتی نداشت."
    return head


async def toll_payers_slice(payer_id: int, non_tax_income: float) -> list[tuple[int, int]]:
    """محاسبه عوارض تنگه برای یک پرداخت‌کننده: [(مالک، مبلغ)]."""
    country = await get_country(payer_id)
    if not country or not country.get("has_sea"):
        return []
    pct = float(await get_setting("strait_toll_percent", "1.5")) / 100
    sec_on = await get_setting("sec_straits", "1")
    if sec_on != "1":
        return []
    rows = await db.fetchall(
        "SELECT s.owner_id, c.has_sea FROM straits s JOIN countries c ON c.owner_id=s.owner_id "
        "WHERE s.is_active=1 AND s.owner_id IS NOT NULL AND s.owner_id!=?", (payer_id,))
    out = []
    for r in rows:
        if not r["has_sea"]:  # مالکِ بدون مرز دریایی درآمدی از تنگه نمی‌گیرد
            continue
        out.append((r["owner_id"], int(non_tax_income * pct)))
    return out


async def straits_menu_text(user_id: int) -> tuple[str, list]:
    """متن و دکمه‌های بخش تنگه‌ها همراه با قابلیت انسداد تنگه."""
    rows_db = await db.fetchall("SELECT * FROM straits WHERE is_active=1 ORDER BY id")
    my = await naval_power(user_id)
    mine = await my_straits(user_id)
    
    # تنگه‌هایی که علیه من مسدود شده‌اند
    my_blocked = await db.fetchall(
        "SELECT b.*, s.name AS strait_name, s.emoji AS strait_emoji FROM strait_blockades b "
        "JOIN straits s ON s.id=b.strait_id WHERE b.target_user_id=?", (user_id,))

    lines = ["⚓ <b>تنگه‌های راهبردی دنیا و امنیت دریانوردی</b>\n",
             f"🚢 قدرت دریایی شما: <b>{fmt(my)}</b> (ناو/زیردریایی/قایق/ناوشکن)",
             f"🏝 تنگه‌های تحت حاکمیت شما: <b>{len(mine)}</b>"]
    
    if my_blocked:
        lines.append(f"\n🚫 <b>هشدار: {len(my_blocked)} تنگه روی کشور شما مسدود است!</b>")
        lines.append(f"افت درآمد ناشی از انسداد: <b>{len(my_blocked) * 10}٪</b> از کل درآمد نوبتی")
        for mb in my_blocked:
            lines.append(f"  • {mb['strait_emoji']} تنگه {mb['strait_name']}")

    lines.append("\n<b>وضعیت تنگه‌ها در آبراه‌های بین‌المللی:</b>")
    buttons = []
    for s in rows_db:
        owner = await get_country(s["owner_id"]) if s["owner_id"] else None
        if s["owner_id"] == user_id:
            status = "👑 مالک: شما"
        elif owner:
            d_def = await naval_defense(s["owner_id"])
            status = (f"🏳 مالک: {owner['flag']} {owner['name']} — 🛡 دفاع دریایی: {fmt(d_def)}")
        else:
            status = "🆓 بدون مالک"
        lines.append(f"• {s['emoji']} <b>{s['name']}</b> — {status}")
        if s["owner_id"] != user_id:
            buttons.append([(f"⚔️ حمله دریایی برای تسخیر {s['name']}", f"g|stc|{s['id']}")])
    
    if mine:
        lines.append("\n💰 عوارض تنگه‌ها: ۱.۵٪ درآمد غیرمالیاتی هر کشور دارای مرز دریایی به شما می‌رسد.")
        lines.append("🚫 <b>قابلیت انسداد:</b> شما می‌توانید تنگه خود را روی هر کشوری ببندید تا ۱۰٪ درآمدش کسر شود.")
        buttons.append([("🚫 مدیریت انسداد تنگه‌ها (کاهش درآمد کشور هدف)", "g|stblk_menu")])

    lines.append("\n⚔️ <b>تسخیر تنگه = نبرد دریایی واقعی:</b> توان ناوگان شما با ناوگان + پدافند ساحلی مالک "
                 "سنجیده می‌شود، نتیجه بر اساس نسبت قدرت تعیین می‌گردد و <b>هر دو طرف</b> تلفات واقعی "
                 "می‌دهند (کسر از انبار). گزارش استراتژی حمله و خسارات دو طرف در کانال اعلام می‌شود.")
    lines.append("♻️ <b>حمله همیشه ممکن است:</b> اگر ناوگانتان از مدافع ضعیف‌تر باشد، نبرد "
                 "<b>فرسایشی</b> می‌شود — با هر حمله بخشی از ناوگان مدافع از بین می‌رود تا دفاعش بشکند.")
    lines.append("⚠️ کشورهای بدون مرز دریایی نه عوارض می‌پردازند و نه درآمد تنگه دارند.")
    return "\n".join(lines), buttons


async def get_owner_blockades(owner_id: int) -> list[dict]:
    """دریافت تمام انسدادهای فعال توسط این مالک."""
    return await db.fetchall(
        "SELECT b.*, s.name AS strait_name, s.emoji AS strait_emoji, c.name AS target_name, c.flag AS target_flag "
        "FROM strait_blockades b JOIN straits s ON s.id=b.strait_id "
        "JOIN users u ON u.id=b.target_user_id "
        "LEFT JOIN countries c ON c.id=u.country_id "
        "WHERE b.owner_id=?", (owner_id,))


async def toggle_strait_blockade(owner_id: int, strait_id: int, target_user_id: int) -> tuple[bool, str]:
    """فعال یا غیرفعال کردن انسداد یک تنگه روی کشور هدف."""
    strait = await db.fetchone("SELECT * FROM straits WHERE id=? AND owner_id=?", (strait_id, owner_id))
    if not strait:
        return False, "❌ شما مالک این تنگه نیستید!"
    
    target_country = await get_country(target_user_id)
    if not target_country:
        return False, "❌ کشور هدف نامعتبر است."

    exists = await db.fetchone(
        "SELECT id FROM strait_blockades WHERE strait_id=? AND target_user_id=?",
        (strait_id, target_user_id))
    
    if exists:
        await db.execute("DELETE FROM strait_blockades WHERE id=?", (exists["id"],))
        await log_event("strait", f"{strait['name']} برای کشور {target_country['name']} بازگشایی شد")
        return False, f"🟢 {strait['name']} برای کشور {target_country['flag']} {target_country['name']} باز شد."
    else:
        await db.execute(
            "INSERT INTO strait_blockades(strait_id, owner_id, target_user_id) VALUES(?,?,?)",
            (strait_id, owner_id, target_user_id))
        await log_event("strait", f"{strait['name']} روی کشور {target_country['name']} مسدود شد (-10% درآمد)")
        return True, f"🚫 {strait['name']} با موفقیت روی {target_country['flag']} {target_country['name']} مسدود شد!\n۱۰٪ از درآمد ملی این کشور کسر می‌شود."
