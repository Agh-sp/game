"""تنگه‌های راهبردی — قدرت دریایی، تصاحب، عوارض ۱.۵٪ درآمد غیرمالیاتی."""
from core.db import db, get_setting
from core.economy import get_country
from core.events import log_event
from core.images import announce_img
from core.utils import fmt, iso


async def naval_power(user_id: int) -> int:
    """قدرت دریایی = مجموع توان (حمله+دفاع) تجهیزات دسته دریایی (ناو/زیردریایی/قایق/...)."""
    rows = await db.fetchall(
        "SELECT a.quantity, (e.attack_power + e.defense_power) AS power FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id "
        "JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND c.key='sea'", (user_id,))
    return int(sum(r["quantity"] * (r["power"] or 0) for r in rows))


async def my_straits(user_id: int) -> list[dict]:
    return await db.fetchall("SELECT * FROM straits WHERE owner_id=? ORDER BY id", (user_id,))


async def capture_requirements(user_id: int, strait: dict) -> tuple[bool, str]:
    """آیا این کشور می‌تواند تنگه را تصاحب کند؟"""
    country = await get_country(user_id)
    if not country or not country.get("has_sea"):
        return False, "❌ کشور شما مرز دریایی ندارد!"
    my = await naval_power(user_id)
    if not strait["owner_id"] or strait["owner_id"] == user_id:
        need = int(float(await get_setting("strait_min_naval", "500")))
        if my < need:
            return False, f"❌ برای تصاحب تنگه آزاد حداقل {fmt(need)} قدرت دریایی لازم است (شما: {fmt(my)})."
        return True, ""
    if strait["owner_id"] == user_id:
        return False, "شما مالک این تنگه هستید."
    owner_country = await get_country(strait["owner_id"])
    owner_power = await naval_power(strait["owner_id"])
    ratio = float(await get_setting("strait_capture_ratio", "2.5"))
    need = int(owner_power * ratio)
    if my < need:
        return False, (f"❌ برای گرفتن تنگه از {owner_country['name'] if owner_country else 'مالک'} "
                       f"باید حداقل {fmt(need)} قدرت دریایی داشته باشید "
                       f"(۲.۵ برابر قدرت او: {fmt(owner_power)}). شما: {fmt(my)}.")
    return True, ""


async def capture_strait(bot, user_id: int, strait_id: int) -> str:
    """تصاحب تنگه با شرط قدرت دریایی، نبرد دریایی واقعی، تلفات ناوگان و اعلان کانال با عکس."""
    s = await db.fetchone("SELECT * FROM straits WHERE id=? AND is_active=1", (strait_id,))
    if not s:
        return "تنگه یافت نشد."
    ok, err = await capture_requirements(user_id, s)
    if not ok:
        return err
    old_owner = s["owner_id"]
    old_country = await get_country(old_owner) if old_owner else None
    me = await get_country(user_id)
    my_pow = await naval_power(user_id)

    # شبیه‌سازی درگیری دریایی و وارد کردن تلفات به ناوگان طرفین
    atk_fleet_losses = []
    def_fleet_losses = []

    # محاسبه و کسر تلفات از ناوگان تصاحب‌کننده (۵ تا ۱۵ درصد ناوگان مهاجم)
    my_ships = await db.fetchall(
        "SELECT a.item_id, a.quantity, e.name, e.emoji FROM player_assets a "
        "JOIN equipment e ON e.id=a.item_id JOIN equipment_categories c ON c.id=e.category_id "
        "WHERE a.user_id=? AND a.item_type='equipment' AND c.key='sea' AND a.quantity>0", (user_id,))
    from core.economy import sub_asset
    for ship in my_ships:
        lost = max(1, int(ship["quantity"] * 0.10)) if ship["quantity"] > 5 else (1 if ship["quantity"] > 2 else 0)
        if lost > 0:
            await sub_asset(user_id, "equipment", ship["item_id"], lost)
            atk_fleet_losses.append(f"{lost}× {ship['emoji']} {ship['name']}")

    # اگر تنگه مالک داشت، نبرد تمام‌عیار رخ داده و تلفات سنگین به ناوگان مالک قبلی وارد می‌شود
    battle_dispatch = ""
    if old_owner and old_owner != user_id:
        enemy_ships = await db.fetchall(
            "SELECT a.item_id, a.quantity, e.name, e.emoji FROM player_assets a "
            "JOIN equipment e ON e.id=a.item_id JOIN equipment_categories c ON c.id=e.category_id "
            "WHERE a.user_id=? AND a.item_type='equipment' AND c.key='sea' AND a.quantity>0", (old_owner,))
        for eship in enemy_ships:
            # نابودی ۳۰ تا ۵۰ درصد از ناوگان مدافع در این تنگه
            def_lost = max(1, int(eship["quantity"] * 0.40)) if eship["quantity"] > 2 else eship["quantity"]
            if def_lost > 0:
                await sub_asset(old_owner, "equipment", eship["item_id"], def_lost)
                def_fleet_losses.append(f"{def_lost}× {eship['emoji']} {eship['name']}")

        # کاهش رضایت عمومی کشور مدافع به دلیل از دست دادن تنگه استراتژیک
        await db.execute("UPDATE states SET satisfaction=MAX(0, satisfaction-5) WHERE user_id=?", (old_owner,))

        battle_dispatch = (
            f"\n🔥 <b>گزارش نبرد سنگین دریایی:</b>\n"
            f"ناوگان جنگی {me['flag']} <b>{me['name']}</b> با قدرت آتش سنگین به استحکامات و گشت‌های دریایی "
            f"{old_country['flag']} <b>{old_country['name']}</b> حمله بردند.\n"
        )
        if def_fleet_losses:
            battle_dispatch += f"💥 ناوگان منهدم‌شده {old_country['name']}: " + " ، ".join(def_fleet_losses[:4]) + "\n"
        if atk_fleet_losses:
            battle_dispatch += f"⚓ تلفات ناوگان مهاجم {me['name']}: " + " ، ".join(atk_fleet_losses[:3]) + "\n"

    # ثبت مالک جدید
    await db.execute("UPDATE straits SET owner_id=?, captured_at=? WHERE id=?",
                     (user_id, iso(), strait_id))
    await log_event("strait", f"{me['name']} پس از نبرد دریایی تنگه {s['name']} را تصاحب کرد")

    if old_owner and old_owner != user_id:
        try:
            alert_msg = (
                f"🚨 <b>هشدار فوری جنگی!</b>\n\n"
                f"ناوگان دریایی {me['flag']} <b>{me['name']}</b> به مواضع شما در <b>{s['name']}</b> حمله کردند!\n"
                f"تنگه از کنترل شما خارج شد و ناوگان شما متحمل تلفات گردید."
            )
            if def_fleet_losses:
                alert_msg += "\n💥 شناورهای آسیب‌دیده: " + " ، ".join(def_fleet_losses[:4])
            await bot.send_message(old_owner, alert_msg)
        except Exception:
            pass

    announcement_text = (
        f"⚓ <b>تسخیر استراتژیک تنگه {s['name']}!</b>\n\n"
        f"نیروهای دریایی کشور {me['flag']} <b>{me['name']}</b> با برتری ناوگان نظامی خود کنترل کامل آبراه "
        f"<b>{s['name']}</b> را در دست گرفتند!\n"
    )
    if old_country:
        announcement_text += f"طرف شکست‌خورده: {old_country['flag']} <b>{old_country['name']}</b>\n"
    else:
        announcement_text += "این آبراه پیش از این بدون حاکمیت دفاعی مستقر بود.\n"

    if battle_dispatch:
        announcement_text += battle_dispatch

    await announce_img(bot, announcement_text, "strait")

    res_summary = f"✅ تنگه {s['name']} پس از نبرد با موفقیت به تصرف درآمد!\n۱.۵٪ عوارض ترانزیت جهانی به حساب شما واریز خواهد شد."
    if atk_fleet_losses:
        res_summary += f"\n💥 تلفات ناوگان شما در عملیات: {' ، '.join(atk_fleet_losses[:3])}"
    return res_summary


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
            status = f"🏳 مالک: {owner['flag']} {owner['name']}"
        else:
            status = "🆓 بدون مالک"
        lines.append(f"• {s['emoji']} <b>{s['name']}</b> — {status}")
        if s["owner_id"] != user_id:
            buttons.append([(f"⚔️ تصاحب {s['name']}", f"g|stc|{s['id']}")])
    
    if mine:
        lines.append("\n💰 عوارض تنگه‌ها: ۱.۵٪ درآمد غیرمالیاتی هر کشور دارای مرز دریایی به شما می‌رسد.")
        lines.append("🚫 <b>قابلیت انسداد:</b> شما می‌توانید تنگه خود را روی هر کشوری ببندید تا ۱۰٪ درآمدش کسر شود.")
        buttons.append([("🚫 مدیریت انسداد تنگه‌ها (کاهش درآمد کشور هدف)", "g|stblk_menu")])

    lines.append("\n⚠️ کشورهای بدون مرز دریایی نه عوارض می‌پردازند و نه درآمد تنگه دارند.")
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
        await log_event("strait", f"تنگه {strait['name']} برای کشور {target_country['name']} بازگشایی شد")
        return False, f"🟢 تنگه {strait['name']} برای کشور {target_country['flag']} {target_country['name']} باز شد."
    else:
        await db.execute(
            "INSERT INTO strait_blockades(strait_id, owner_id, target_user_id) VALUES(?,?,?)",
            (strait_id, owner_id, target_user_id))
        await log_event("strait", f"تنگه {strait['name']} روی کشور {target_country['name']} مسدود شد (-10% درآمد)")
        return True, f"🚫 تنگه {strait['name']} با موفقیت روی {target_country['flag']} {target_country['name']} مسدود شد!\n۱۰٪ از درآمد ملی این کشور کسر می‌شود."
