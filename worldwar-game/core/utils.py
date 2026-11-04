"""ابزارهای مشترک: زمان، فرمت اعداد، متن و کلیدهای فشرده."""
import json
from datetime import datetime, timedelta, timezone

TEHRAN_OFFSET = timedelta(hours=3, minutes=30)


def now() -> datetime:
    """زمان فعلی UTC (بدون microseconds تا با فرمت SQLite یکسان باشد)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def iso(dt: datetime | None = None) -> str:
    """فرمت استاندارد ذخیره timestamps: YYYY-MM-DD HH:MM:SS (UTC)."""
    dt = dt or now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def add_hours(hours: float) -> str:
    return iso(now() + timedelta(hours=hours))


def is_past(s: str | None) -> bool:
    dt = parse(s)
    return dt is not None and dt <= now()


def hours_left(s: str | None) -> float:
    dt = parse(s)
    if dt is None:
        return 0.0
    return max(0.0, (dt - now()).total_seconds() / 3600)


def hours_ago(s: str | None) -> float:
    """چند ساعت از یک زمان گذشته است (برای cooldown‌ها؛ آینده → ۰)."""
    dt = parse(s)
    if dt is None:
        return 1_000_000.0
    return max(0.0, (now() - dt).total_seconds() / 3600)


def fmt_hm(hours: float) -> str:
    """مدت باقی‌مانده به شکل خوانا."""
    if hours <= 0:
        return "۰"
    total = int(hours * 60)
    h, m = divmod(total, 60)
    if h >= 24:
        d, h = divmod(h, 24)
        return f"{d} روز و {h} ساعت"
    if h > 0:
        return f"{h} ساعت و {m} دقیقه"
    return f"{m} دقیقه"


def tehran(s: str | None) -> str:
    """نمایش زمان به ساعت تهران."""
    dt = parse(s)
    if dt is None:
        return "—"
    return (dt + TEHRAN_OFFSET).strftime("%Y-%m-%d %H:%M")


def day_str() -> str:
    """کلید روز جاری برای ماموریت‌های روزانه."""
    return now().strftime("%Y-%m-%d")


def fmt(n) -> str:
    """جداکننده هزارگان."""
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def _trim(x: float) -> str:
    """عدد اعشاری بدون صفرهای انتهایی."""
    if abs(x - round(x)) < 0.05:
        return f"{int(round(x)):,}"
    return f"{round(x, 2):,}".rstrip("0").rstrip(".")


def fmt_money(n) -> str:
    """نمایش مبلغ به شکل خوانا و «میلیونی» — مثلاً ۲۵۰ میلیون یا ۱.۵ میلیارد.

    بازیکن‌ها مبالغ را در مقیاس میلیون می‌بینند، نه با ۹ رقم صفر.
    """
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        return str(n)
    neg = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{neg}{_trim(v / 1_000_000_000)} میلیارد"
    if v >= 1_000_000:
        return f"{neg}{_trim(v / 1_000_000)} میلیون"
    if v >= 1_000:
        return f"{neg}{_trim(v / 1_000)} هزار"
    return f"{neg}{_trim(v)}"


def fmt_money_full(n) -> str:
    """نمای میلیونی + عدد دقیق داخل پرانتز (برای گزارش‌های مالی)."""
    exact = fmt(n)
    short = fmt_money(n)
    return short if short == exact else f"{short} ({exact})"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def pct(x: float) -> str:
    return f"{round(float(x), 1)}%"


def fa_bool(v) -> str:
    return "✅" if v else "❌"


def split_text(text: str, limit: int = 3800) -> list[str]:
    """شکستن متن‌های طولانی برای ارسال در تلگرام."""
    parts, chunk = [], ""
    for line in text.split("\n"):
        if len(chunk) + len(line) + 1 > limit:
            parts.append(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        parts.append(chunk)
    return parts


def jloads(s, default=None):
    if default is None:
        default = {}
    if not s:
        return default
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return default


def jdumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def b36(n: int) -> str:
    n = int(n)
    if n == 0:
        return "0"
    neg, out = n < 0, ""
    n = abs(n)
    while n:
        n, r = divmod(n, 36)
        out = ALPHABET[r] + out
    return ("-" + out) if neg else out


def unb36(s: str) -> int:
    try:
        return int(s, 36)
    except (ValueError, TypeError):
        return 0


def progress_bar(value: float, total: float, width: int = 10) -> str:
    if total <= 0:
        return "▬" * width
    filled = int(clamp(value / total, 0, 1) * width)
    return "█" * filled + "▬" * (width - filled)
