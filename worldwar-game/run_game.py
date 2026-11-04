"""اجرای فقط ربات اصلی بازی."""
import asyncio

from gamebot.main import run

if __name__ == "__main__":
    asyncio.run(run())
