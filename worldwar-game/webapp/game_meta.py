"""فراداده و آمار بازی برای پنل فرماندهی + شبیه‌ساز نبرد.

این ماژول جایگزین پایتونی همان بخش‌هایی از `server.ts` است که آمار/معماری بازی و
محاسبهٔ نتیجهٔ نبرد را برمی‌گرداند. تا حد امکان از دیتابیس واقعی بازی خوانده
می‌شود و در صورت خالی بودن، مقادیر پیش‌فرض معتبر برمی‌گردد.
"""
from __future__ import annotations

import random
from typing import Any

from core import config as cfg

from . import data_service


def _count(sql: str) -> int | None:
    try:
        conn = data_service.connect()
        try:
            return int(conn.execute(sql).fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return None


def metadata() -> dict[str, Any]:
    countries = _count("SELECT COUNT(*) FROM countries")
    free = _count("SELECT COUNT(*) FROM countries WHERE COALESCE(is_special,0)=0")
    special = _count("SELECT COUNT(*) FROM countries WHERE COALESCE(is_special,0)=1")
    equipment = _count("SELECT COUNT(*) FROM equipment")
    straits = _count("SELECT COUNT(*) FROM straits")
    buildings = _count("SELECT COUNT(*) FROM buildings")
    treaties = _count("SELECT COUNT(*) FROM treaties")
    missions = _count("SELECT COUNT(*) FROM daily_missions")
    tables = _count("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")

    return {
        "stats": {
            "totalCountries": countries or 45,
            "freeCountries": free or 15,
            "specialCountries": special or 30,
            "equipmentCount": equipment or 46,
            "straitCount": straits or 8,
            "buildingCount": buildings or 38,
            "treatyCount": treaties or 5,
            "dailyMissionCount": missions or 7,
            "dbTableCount": tables or 48,
        },
        "runtime": {
            "language": "python",
            "server": "worldwar-game/webapp/server.py (aiohttp)",
            "bots": {"game": "run_game.py", "admin": "run_admin.py"},
            "bothBots": "run_all.py",
            "webhook": "run_webhook.py",
            "superAdminId": cfg.SUPER_ADMIN_ID,
            "superAdminIds": list(cfg.SUPER_ADMIN_IDS),
            "gameBotTokenConfigured": bool(cfg.GAME_BOT_TOKEN),
            "adminBotTokenConfigured": bool(cfg.ADMIN_BOT_TOKEN),
            "mode": "webhook" if cfg.WEBHOOK_MODE else "polling",
        },
        "botArchitecture": {
            "gameBot": {
                "file": "run_game.py",
                "description": "ربات تعاملی بازیکنان با کیبوردهای اینلاین، مدیریت امپراطوری، جنگ و تجارت",
                "defaultTokenEnv": "GAME_BOT_TOKEN",
                "menus": [
                    {"key": "empire", "title": "🏰 امپراطوری من",
                     "desc": "مدیریت مردم، پروژه‌های ملی، ارتش، دین و حکومت، درآمد دوره‌ای"},
                    {"key": "daily", "title": "🎯 ماموریت روزانه",
                     "desc": "ماموریت‌های روزانه همراه با جوایز سکه شاهی و پول پایه"},
                    {"key": "royal_coins", "title": "🪙 سکه شاهی",
                     "desc": "خرید پکیج، ارسال عکس فیش کارت‌به‌کارت و تبدیل به پول پایه"},
                    {"key": "war_room", "title": "⚔️ اتاق جنگ",
                     "desc": "اعلان جنگ رسمی یا غافلگیرانه، حملات هوایی/دریایی/زمینی/سایبری/فضایی"},
                    {"key": "un", "title": "🇺🇳 سازمان ملل",
                     "desc": "شورای امنیت، بیانیه رسمی، رأی‌گیری تحریم، خلع سلاح و وتو قدرت‌ها"},
                    {"key": "trade", "title": "🤝 تجارت و تنگه‌ها",
                     "desc": "مذاکره مخفیانه، پیمان‌های بین‌المللی، معاوضه مستقیم و عوارض تنگه‌ها"},
                    {"key": "rescue", "title": "🛟 سازمان نجات",
                     "desc": "کمپین‌های بشردوستانه جنگ، اهدای انرژی و ذخایر اضطراری"},
                    {"key": "oil", "title": "🛢️ صنعت نفت",
                     "desc": "مخازن زیرزمینی، حفاری دکل، استخراج خودکار و فروش به بازار جهانی"},
                ],
            },
            "adminBot": {
                "file": "run_admin.py",
                "description": "پنل مدیریت جامع با دسترسی تفکیک‌شده و مرور مستقیم جدول‌های دیتابیس",
                "defaultTokenEnv": "ADMIN_BOT_TOKEN",
                "permissions": [
                    "کاربران (جستجو، ویرایش دارایی، بن، ریست)",
                    "اقتصاد (قیمت سکه شاهی، شماره کارت، نرخ تبدیل)",
                    "فیش‌ها (تأیید/رد واریزی‌های بازیکنان)",
                    "کشورها (تغییر جمعیت، پرچم، وضعیت ویژه/رایگان)",
                    "نظامی (تغییر قدرت حمله/دفاع، قیمت تجهیزات)",
                    "پروژه‌ها و ساختمان‌ها (تعریف ساختمان، هزینه و اثرات)",
                    "سازمان ملل و جنگ‌ها (مدیریت منازعات، لغو جنگ، بیانیه‌ها)",
                    "ماموریت‌ها (ساخت ماموریت روزانه و تعیین پاداش)",
                    "پشتیبانی (پاسخ دوطرفه به تیکت‌های بازیکنان)",
                    "تنظیمات عمومی (کانال اجباری، کانال اعلانات، متن استارت)",
                    "پیام همگانی (برودکست به کل بازیکنان)",
                    "سیزن‌ها (جنگ جهانی، صلیبی، دوران باستان)",
                    "تنگه‌ها (کنترل عوارض و نبردهای دریایی)",
                    "کتابخانه تصاویر (آیدی عکس رویدادها)",
                    "افزودن انبوه تجهیزات",
                    "دیتابیس خام (مشاهده و ادیت جدول‌های SQLite)",
                ],
            },
        },
        "quickPanel": {
            "command": "/panel",
            "description": "پنل سریع ادمین داخل ربات بازی (واریز/برداشت، بن، فیش، برودکست)",
            "superAdminIds": list(cfg.SUPER_ADMIN_IDS),
        },
    }


def simulate_battle(attacker: dict[str, Any], defender: dict[str, Any]) -> dict[str, Any]:
    """شبیه‌سازی نبرد — همان فرمول نسخهٔ قبلی پنل (سازگار با core/combat.py)."""
    attacker = attacker or {}
    defender = defender or {}
    atk = max(10.0, float(attacker.get("attackPower") or 100))
    dfn = max(10.0, float(defender.get("defensePower") or 100))
    cyber_adv = float(attacker.get("cyberPower") or 0) - float(defender.get("cyberPower") or 0)

    luck = 0.85 + random.random() * 0.3
    effective_atk = atk * luck * (1.1 if cyber_adv > 0 else 0.95)
    ratio = effective_atk / (effective_atk + dfn)

    is_victory = ratio > 0.52
    attacker_loss = (max(0.05, (1 - ratio) * 0.4) if is_victory
                     else 0.35 + (1 - ratio) * 0.3)
    defender_loss = (0.4 + ratio * 0.3 if is_victory
                     else max(0.08, ratio * 0.3))
    spoils = int(float(defender.get("treasury") or 200_000_000) * 0.15) if is_victory else 0

    return {
        "isVictory": is_victory,
        "combatRatio": round(ratio * 100, 1),
        "luckMultiplier": round(luck, 2),
        "attackerLossPercent": round(attacker_loss * 100, 1),
        "defenderLossPercent": round(defender_loss * 100, 1),
        "spoilsOfWarMoney": spoils,
        "log": [
            f"قدرت تهاجمی موثر مهاجم: {int(effective_atk):,}",
            f"قدرت تدافعی مدافع: {int(dfn):,}",
            f"برتری سایبری: {'+' if cyber_adv >= 0 else ''}{int(cyber_adv):,}",
            ("پیروزی قاطع نیروهای مهاجم! ۱۵٪ از خزانهٔ کشور مدافع غنیمت گرفته شد."
             if is_victory else
             "شکست حمله! مدافعان خطوط دفاعی خود را حفظ کردند و تلفات سنگینی به مهاجم وارد شد."),
        ],
    }
