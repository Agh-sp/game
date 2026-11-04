"""Shared harness helpers for testing worldwar-game bots without Telegram."""
import asyncio, os, sys, traceback, random
from datetime import datetime, timezone

os.environ.setdefault("SUPER_ADMIN_ID", "999")
DB = os.environ.get("TEST_DB", "/tmp/t/test.db")
os.environ["DB_PATH"] = DB
for suffix in ("", "-wal", "-shm"):
    p = DB + suffix
    if os.path.exists(p):
        os.remove(p)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message as TGMessage, Update, User as TGUser

ERRORS = []
SENT = []
BOT_REF = {}


def _safe_cid(chat_id):
    try:
        return int(chat_id)
    except (TypeError, ValueError):
        return 1


class FakeBot(Bot):
    async def __call__(self, method, request_timeout=None):
        name = getattr(method, "__api_method__", type(method).__name__)
        text = getattr(method, "text", None) or getattr(method, "caption", None)
        chat_id = getattr(method, "chat_id", None)
        if name == "getMe":
            return TGUser(id=42, is_bot=True, first_name="Test", username="test_bot")
        SENT.append((name, chat_id, text, getattr(method, "photo", None)))
        if name in ("sendMessage", "sendPhoto", "editMessageText"):
            return TGMessage(message_id=1, date=datetime.now(timezone.utc),
                             chat=Chat(id=_safe_cid(chat_id), type="private"), text=text or "")
        return True


def tg_uid(uid):
    return TGUser(id=uid, is_bot=False, first_name=f"U{uid}", username=f"u{uid}")


def cb_update(uid, data):
    msg = TGMessage(message_id=10, date=datetime.now(timezone.utc),
                    chat=Chat(id=uid, type="private"), text="prev").as_(BOT_REF["bot"])
    return Update(update_id=1, callback_query=CallbackQuery(
        id="cb1", from_user=tg_uid(uid), chat_instance="ci", data=data, message=msg))


def msg_update(uid, text):
    m = TGMessage(message_id=11, date=datetime.now(timezone.utc), chat=Chat(id=uid, type="private"),
                  from_user=tg_uid(uid), text=text)
    return Update(update_id=2, message=m.as_(BOT_REF["bot"]))


async def make_world(users):
    """users: [(uid, name, country_index)] — country taken via users.country_id only."""
    from core.db import init_db, db
    await init_db()
    rows = await db.fetchall("SELECT * FROM countries WHERE is_active=1 ORDER BY id")
    for uid, name, idx in users:
        await db.execute("INSERT OR IGNORE INTO users(id, full_name, joined_at) VALUES(?,?,datetime('now'))",
                         (uid, name))
        c = rows[idx]
        await db.execute("UPDATE users SET country_id=?, money=1000000000 WHERE id=?", (c["id"], uid))
        await db.execute("UPDATE countries SET owner_id=NULL WHERE id=?", (c["id"],))
        await db.execute(
            "INSERT OR IGNORE INTO states(user_id, satisfaction, cyber_power) VALUES(?,50,10000)", (uid,))
    return rows


async def new_game_dp():
    from gamebot.main import create_dispatcher
    dp = create_dispatcher()
    bot = FakeBot("42:GAME")
    BOT_REF["bot"] = bot

    async def err(event):
        ERRORS.append(f"{type(event.exception).__name__}: {event.exception}")
        traceback.print_exception(type(event.exception), event.exception,
                                  event.exception.__traceback__, limit=6)
        return True
    dp.errors.register(err)
    return dp, bot


async def new_admin_dp():
    from adminbot.main import create_dispatcher
    dp = create_dispatcher()
    bot = FakeBot("43:ADMIN")
    BOT_REF["bot"] = bot

    async def err(event):
        ERRORS.append(f"ADMIN {type(event.exception).__name__}: {event.exception}")
        traceback.print_exception(type(event.exception), event.exception,
                                  event.exception.__traceback__, limit=6)
        return True
    dp.errors.register(err)
    return dp, bot


def shot(label):
    texts = [t for (_n, _c, t, _p) in SENT if t]
    photos = [p for (_n, _c, _t, p) in SENT if p]
    print(f"  [{label}] msgs={len(SENT)} photos={len(photos)}")
    for t in texts[:4]:
        print("     >", t.replace("\n", " | ")[:220])
    return texts, photos


def check(cond, label):
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        ERRORS.append("CHECK FAILED: " + label)
    return cond
