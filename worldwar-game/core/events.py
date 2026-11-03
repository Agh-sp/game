"""ثبت رویدادهای بازی برای گزارش روزانه ادمین + میرroring روی سرور فایربیس."""
from core.db import db
from core.firebase import fb
from core.utils import iso


async def log_event(kind: str, text: str) -> None:
    """ثبت رویداد (جنگ/پیمان/تجارت/نفت/تنگه/ارز/درآمد/...)."""
    try:
        await db.execute(
            "INSERT INTO game_events(kind, text) VALUES(?,?)",
            (kind, text[:500]))
    except Exception:
        pass
    try:
        await fb.mirror(f"game/events/{iso().replace('-', '').replace(':', '').replace(' ', '_')}",
                        {"kind": kind, "text": text[:300], "at": iso()})
    except Exception:
        pass
