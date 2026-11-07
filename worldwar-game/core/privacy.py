"""🔒 نمایش هویت محرمانهٔ بازیکن‌ها در همهٔ لیست‌ها و گزارش‌ها.

به‌درخواست کاربر، **هیچ آیدی یا یوزرنیم تلگرامی** نباید در بازی نمایش داده شود.
به‌جای آن یک «نام فرمانده» ساختگی و ثابت برای هر کاربر ساخته می‌شود:

    👤 🇮🇷 ایران — فرمانده: ح.م

نام فرمانده از حرف اول نام نمایشی تلگرام + یک حرف دوم تصادفی (seed = آیدی)
ساخته می‌شود تا برای یک بازیکن همیشه یکسان و برای بقیه غیرقابل‌حدس باشد، ولی
**هیچ وقفی از یوزرنیم واقعی در آن نیست**.
"""
from __future__ import annotations

import html

from core.db import db

# حروفی که برای مخفی‌سازی نام استفاده می‌شود
_MASK_CHARS = list("ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی")


def mask_name(raw: str | None, seed: int = 0) -> str:
    """ساخت نام مستعار از یک نام واقعی — بدون هیچ نشانی از متن اصلی."""
    seed = abs(int(seed or 0))
    letters: list[str] = []
    if raw:
        for ch in raw.strip():
            if ch in _MASK_CHARS and ch not in letters:
                letters.append(ch)
            if len(letters) >= 2:
                break
    while len(letters) < 2:
        letters.append(_MASK_CHARS[seed % len(_MASK_CHARS)])
        seed += 7
    return f"{letters[0]}.{letters[1]}"


async def commander_name(user_id: int) -> str:
    """نام فرماندهٔ محرمانهٔ یک بازیکن (ثابت و غیرقابل ردیابی)."""
    try:
        row = await db.fetchone(
            "SELECT full_name, username FROM users WHERE id=?", (user_id,))
    except Exception:
        row = None
    raw = (row or {}).get("full_name") or (row or {}).get("username") or ""
    return mask_name(raw, user_id)


async def label(user_id: int, country: dict | None = None,
                anonymous: bool = True) -> str:
    """برچسب کامل کشور + فرمانده برای دکمه‌ها و متن‌ها.

    ``anonymous=False`` فقط برای ادمین‌ها استفاده شود.
    """
    from core.economy import get_country

    c = country or await get_country(user_id)
    if not c:
        return "؟"
    base = f"{c['flag']} {html.escape(c['name'])}"
    if not anonymous:
        return base
    return f"{base} — فرمانده: {await commander_name(user_id)}"


def label_plain(country: dict | None, user_id: int = 0, name: str = "") -> str:
    """نسخهٔ همگام برای وقتی دادهٔ کشور از قبل داریم (بدون کوئری اضافه)."""
    if not country and not name:
        return "؟"
    flag = (country or {}).get("flag") or ""
    cname = (country or {}).get("name") or name or "؟"
    return f"{flag} {cname}".strip()
