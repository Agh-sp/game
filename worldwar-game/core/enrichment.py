"""مراحل غنی‌سازی اورانیوم — از ۳.۵٪ تا ۹۰٪، مرحله به مرحله.

هر مرحله باید جداگانه اجرا شود و مرحلهٔ بعد فقط پس از تکمیل مرحلهٔ قبل باز می‌شود.
تکمیل ۲۰٪ پیش‌نیاز پروژهٔ «غنی‌سازی اورانیوم ۲۰٪» و نیروگاه/زیردریایی هسته‌ای است.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from core.db import db, get_setting
from core.utils import fmt_money, iso, is_past

log = logging.getLogger(__name__)

# (stage, عنوان, درصد, هزینه پول, هزینه مصالح, هزینه سکه, مدت ساعت)
STAGES = [
    (1, "غنی‌سازی ۳٫۵٪ (سوخت نیروگاه)", "۳٫۵٪", 60_000_000, 2_000, 0, 2),
    (2, "غنی‌سازی ۲۰٪ (سوخت راکتور)", "۲۰٪", 150_000_000, 5_000, 0, 4),
    (3, "غنی‌سازی ۶۰٪ (درجه نظامی)", "۶۰٪", 400_000_000, 12_000, 5, 8),
    (4, "غنی‌سازی ۹۰٪ (کلاهک هسته‌ای)", "۹۰٪", 900_000_000, 25_000, 15, 12),
]
MAX_STAGE = STAGES[-1][0]


def stage_info(stage: int) -> tuple | None:
    for s in STAGES:
        if s[0] == stage:
            return s
    return None


async def get_state(user_id: int) -> dict:
    row = await db.fetchone("SELECT * FROM enrichment WHERE user_id=?", (user_id,))
    if not row:
        await db.execute("INSERT OR IGNORE INTO enrichment(user_id, stage) VALUES(?,0)",
                         (user_id,))
        row = await db.fetchone("SELECT * FROM enrichment WHERE user_id=?", (user_id,))
    return dict(row) if row else {"user_id": user_id, "stage": 0,
                                  "started_at": None, "completes_at": None}


async def in_progress(user_id: int) -> bool:
    st = await get_state(user_id)
    return bool(st.get("completes_at")) and not is_past(st["completes_at"])


async def can_start(user_id: int, stage: int) -> tuple[bool, str]:
    st = await get_state(user_id)
    current = int(st.get("stage") or 0)
    if stage != current + 1:
        return False, (f"❌ شما باید اول مرحلهٔ {current + 1} را انجام دهید "
                       f"(پیشرفت فعلی: {current}/{MAX_STAGE}).")
    if await in_progress(user_id):
        return False, "⏳ یک مرحلهٔ غنی‌سازی در جریان است. صبر کنید تا تمام شود."
    info = stage_info(stage)
    if not info:
        return False, "❌ مرحلهٔ نامعتبر."
    _s, title, _pct, cost_money, cost_mat, cost_coins, _hours = info
    user = await db.fetchone("SELECT money FROM users WHERE id=?", (user_id,))
    money = int((user or {}).get("money") or 0)
    if money < cost_money:
        return False, (f"❌ پول کافی ندارید.\n💰 نیاز: {fmt_money(cost_money)}\n"
                       f"💰 خزانه: {fmt_money(money)}")
    state = await db.fetchone("SELECT materials FROM states WHERE user_id=?", (user_id,))
    mats = int((state or {}).get("materials") or 0)
    if mats < cost_mat:
        return False, (f"❌ مصالح کافی ندارید.\n🧱 نیاز: {cost_mat:,} واحد\n"
                       f"🧱 موجودی: {mats:,} واحد\n"
                       "💡 از «🧱 خرید مصالح» در پادگان بخرید.")
    return True, ""


async def start_stage(user_id: int, stage: int) -> tuple[bool, str]:
    ok, err = await can_start(user_id, stage)
    if not ok:
        return False, err
    info = stage_info(stage)
    _s, title, _pct, cost_money, cost_mat, cost_coins, hours = info
    await db.execute("UPDATE users SET money=money-? WHERE id=?", (cost_money, user_id))
    await db.execute("UPDATE states SET materials=MAX(0,materials-?) WHERE user_id=?",
                     (cost_mat, user_id))
    if cost_coins:
        await db.execute("UPDATE users SET royal_coins=MAX(0,royal_coins-?) WHERE id=?",
                         (cost_coins, user_id))
    now = datetime.now(timezone.utc)
    completes = (now + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        "UPDATE enrichment SET started_at=?, completes_at=? WHERE user_id=?",
        (iso(now), completes, user_id))
    return True, (f"☢️ <b>{title}</b> آغاز شد.\n"
                  f"⏳ زمان تکمیل: <b>{hours} ساعت</b>\n"
                  f"📅 اتمام: {completes} (UTC)")


async def settle(user_id: int) -> dict | None:
    """اگر مرحله‌ای کامل شده، آن را ثبت و ارتقا می‌دهد."""
    st = await get_state(user_id)
    if not st.get("completes_at") or not is_past(st["completes_at"]):
        return None
    next_stage = int(st.get("stage") or 0) + 1
    await db.execute(
        "UPDATE enrichment SET stage=?, completes_at=NULL WHERE user_id=?",
        (next_stage, user_id))
    info = stage_info(next_stage)
    title = info[1] if info else f"مرحله {next_stage}"
    try:
        from core.events import log_event
        await log_event("science", f"☢️ {title} تکمیل شد")
    except Exception:
        pass
    # 🏭 تأسیسات هسته‌ای با پیشرفت غنی‌سازی ارتقا پیدا می‌کند
    try:
        from core import nuclear
        await nuclear.sync_stage(user_id)
    except Exception:
        pass
    return {"stage": next_stage, "title": title}


async def rollback(user_id: int, stage: int) -> None:
    """📉 عقب‌بردن مرحلهٔ غنی‌سازی پس از تخریب تأسیسات هسته‌ای."""
    stage = max(0, min(MAX_STAGE, int(stage)))
    await db.execute(
        "UPDATE enrichment SET stage=?, completes_at=NULL, started_at=NULL WHERE user_id=?",
        (stage, user_id))
    try:
        from core.events import log_event
        await log_event("science", f"☢️ تأسیسات هسته‌ای تخریب شد — غنی‌سازی به مرحله {stage} "
                                   "عقب رفت")
    except Exception:
        pass


async def settle_all(bot=None) -> int:
    """تکمیل خودکار همهٔ مراحل رسیده (از زمان‌بند)."""
    rows = await db.fetchall(
        "SELECT user_id FROM enrichment WHERE completes_at IS NOT NULL")
    done = 0
    for r in rows:
        uid = int(r["user_id"])
        res = await settle(uid)
        if not res:
            continue
        done += 1
        if bot:
            try:
                from gamebot.common import kb
                await bot.send_message(
                    uid,
                    f"☢️ <b>مرحلهٔ غنی‌سازی تکمیل شد!</b>\n\n{res['title']}\n"
                    f"پیشرفت: {res['stage']}/{MAX_STAGE}\n"
                    "برای مرحلهٔ بعد وارد بخش «☢️ غنی‌سازی» شوید.",
                    reply_markup=kb([]))
            except Exception:
                pass
    return done


async def make_available(user_id: int) -> None:
    """پس از رسیدن به ۲۰٪، پروژهٔ «غنی‌سازی ۲۰٪» برای این بازیکن آزاد می‌شود."""
    st = await get_state(user_id)
    if int(st.get("stage") or 0) >= 2:
        return
    try:
        b = await db.fetchone("SELECT id FROM buildings WHERE name LIKE '%غنی‌سازی%' LIMIT 1")
        if b:
            await db.execute(
                "DELETE FROM player_projects WHERE user_id=? AND building_id=?",
                (user_id, b["id"]))
    except Exception:
        pass


async def enrichment_text(user_id: int) -> str:
    """متن وضعیت مراحل غنی‌سازی."""
    st = await get_state(user_id)
    current = int(st.get("stage") or 0)
    lines = ["☢️ <b>برنامهٔ غنی‌سازی اورانیوم</b>\n",
             f"📊 پیشرفت شما: <b>{current}/{MAX_STAGE}</b>\n"]
    running = await in_progress(user_id)
    if running:
        lines.append(f"⏳ مرحلهٔ در جریان تا <b>{st['completes_at']}</b> (UTC) تمام می‌شود.\n")
    for s in STAGES:
        idx, title, pct, cost_money, cost_mat, cost_coins, hours = s
        if idx <= current:
            mark = "✅"
        elif idx == current + 1:
            mark = "▶️" if not running else "⏳"
        else:
            mark = "🔒"
        cost = f"{fmt_money(cost_money)}"
        if cost_mat:
            cost += f" + {cost_mat:,} مصالح"
        if cost_coins:
            cost += f" + {cost_coins} سکه"
        lines.append(f"{mark} <b>مرحله {idx}:</b> {title}\n"
                     f"     💰 {cost} • ⏱ {hours} ساعت")
    if current >= MAX_STAGE:
        lines.append("\n🏆 <b>شما به بالاترین مرحلهٔ غنی‌سازی (۹۰٪) رسیده‌اید.</b>")
    else:
        lines.append(f"\n💡 فقط مرحلهٔ {current + 1} قابل شروع است.")
    return "\n".join(lines)
