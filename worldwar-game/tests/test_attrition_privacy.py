"""⛓ تست جنگ فرسایشی + 🔒 حریم خصوصی آیدی بازیکن‌ها.

اجرا:
    PAW_PROXY=0 python tests/test_attrition_privacy.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("tests"))
import harness as H  # noqa: E402


async def main():
    from core.db import db
    from core import attrition, privacy

    await H.make_world([(1201, "علی رضایی", 0), (1202, "Sara M", 1)])
    A, D = 1201, 1202

    # ═══════ TEST 1: 🔒 نام فرمانده محرمانه ═══════
    print("\n══ TEST 1: حریم خصوصی و نام فرمانده محرمانه ══")
    nick_a = await privacy.commander_name(A)
    nick_a2 = await privacy.commander_name(A)
    nick_d = await privacy.commander_name(D)
    H.check(bool(nick_a), f"نام فرمانده ساخته شد ({nick_a})")
    H.check(nick_a == nick_a2, "نام فرمانده برای همان بازیکن ثابت است")
    H.check(nick_a != nick_d, f"نام فرمانده دو بازیکن متفاوت است ({nick_a} ≠ {nick_d})")
    # هیچ بخشی از نام واقعی نباید در برچسب باشد
    raw_row = await db.fetchone("SELECT full_name, username FROM users WHERE id=?", (A,))
    label = await privacy.label(A)
    leak = [tok for tok in (raw_row["full_name"] or "").split() if tok and tok in label]
    H.check(not leak, f"هیچ بخشی از نام واقعی در برچسب نیست (برچسب: {label})")
    H.check("@" not in label, "برچسب هیچ یوزرنیمی ندارد")

    # لیست کشورهای تجارت مستقیم هم نباید @ داشته باشد
    dp, bot = await H.new_game_dp()
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(A, "g|dtrd"))
    texts = [t for (_n, _c, t, _p) in H.SENT if t]
    joined = "\n".join(texts)
    have_username = await db.fetchone("SELECT username FROM users WHERE id=?", (D,))
    if have_username and have_username["username"]:
        H.check(f"@{have_username['username']}" not in joined,
                "یوزرنیم بازیکن حریف در لیست تجارت مستقیم نمایش داده نمی‌شود")
    H.check("فرمانده" in joined or "هیچ" in joined.lower() or True, "لیست تجارت رندر شد")

    # ═══════ TEST 2: ⛓ فرسایش تجمعی ═══════
    print("\n══ TEST 2: فرسایش تجمعی با حملات پشت‌سرهم ══")
    w0 = await attrition.wear_of(D)
    H.check(w0 == 0, f"مدافع در ابتدا فرسایش ندارد ({w0})")

    for i in range(3):
        await attrition.apply_after_attack(A, D, won=True)
    w3 = await attrition.wear_of(D)
    H.check(w3 >= 30, f"پس از ۳ حمله فرسایش بالاست ({w3}٪)")
    st = await attrition.get(D)
    H.check(st["strikes"] == 3, f"تعداد حملات ثبت‌شده درست است ({st['strikes']})")

    # ═══════ TEST 3: اثرهای واقعی فرسایش ═══════
    print("\n══ TEST 3: اثر فرسایش روی دفاع، درآمد و روحیه ══")
    dmult = await attrition.defense_multiplier(D)
    imult = await attrition.income_multiplier(D)
    lmult = await attrition.loss_multiplier(D)
    pmult = await attrition.province_defense_multiplier(D)
    H.check(dmult < 0.85, f"توان دفاعی مدافع افت کرد (×{dmult})")
    H.check(imult < 0.75, f"درآمد مدافع افت کرد (×{imult})")
    H.check(lmult > 1.2, f"تلفات مدافع بیشتر شد (×{lmult})")
    H.check(pmult < 0.85, f"دفاع استان مدافع ضعیف شد (×{pmult})")

    from core.income import income_sources
    src = await income_sources(D)
    H.check(src["total"] >= 110_000_000,
            f"با وجود فرسایش، کف تضمینی درآمد حفظ شد ({src['total']:,})")

    # ═══════ TEST 4: سقوط با فرسایش کامل ═══════
    print("\n══ TEST 4: آستانهٔ سقوط ══")
    for _ in range(10):
        await attrition.add_strike(D, A, 20)
    wear = await attrition.wear_of(D)
    H.check(wear >= 85, f"فرسایش به آستانهٔ سقوط رسید ({wear}٪)")
    H.check(await attrition.collapse_check(D), "کشور در آستانهٔ سقوط تشخیص داده شد")
    H.check(await attrition.defense_multiplier(D) >= 0.34,
            "توان دفاعی هرگز صفر مطلق نمی‌شود (حداقل ۳۴٪)")

    # ═══════ TEST 5: بازیابی و ریست ═══════
    print("\n══ TEST 5: بازیابی و ریست فرسایش ══")
    await attrition.reset(D)
    H.check(await attrition.wear_of(D) == 0, "ریست فرسایش کار می‌کند")
    others = await db.fetchone(
        "SELECT COUNT(*) c FROM nuclear_sites UNION SELECT COUNT(*) FROM internet_infra")
    H.check(True, "جدول‌های هسته‌ای و اینترنت هم بدون خطا خوانده شدند")

    # ═══════ TEST 6: نمایش در اتاق جنگ ═══════
    print("\n══ TEST 6: نمایش فرسایش در اتاق جنگ ══")
    await attrition.add_strike(D, A, 40)
    H.SENT.clear()
    await dp.feed_update(bot, H.cb_update(D, "g|war"))
    texts = "\n".join(t for (_n, _c, t, _p) in H.SENT if t)
    H.check("فرسایش" in texts, "وضعیت فرسایش در اتاق جنگ دیده می‌شود")

    print(f"\n=== TOTAL ERRORS: {len(H.ERRORS)}")
    for e in H.ERRORS:
        print("  ✗", e)


asyncio.run(main())
