#!/usr/bin/env python3
"""
Mass-mailer for Telegram chats using a regular user account.
Requires API_ID and API_HASH from https://my.telegram.org

Usage:
    API_ID=12345 API_HASH=abcdef python mass_mailer.py

First run will prompt for phone number and verification code.
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
from datetime import datetime

from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("mass_mailer")

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
SESSION = os.environ.get("SESSION", "mailer_session")

MIN_DELAY = int(os.environ.get("MIN_DELAY", 300))
MAX_DELAY = int(os.environ.get("MAX_DELAY", 900))

MESSAGE = """🚴 Твои велопоездки приносят деньги. Реально.

Катаешься по одному маршруту? Преврати его в свой актив.

Velo.io — территориальная игра для велосипедистов. Ты выезжаешь маршрут, сервер находит замкнутый контур, и территория твоя. Пока кто-то не перехватит.

Что даёт:
— Соревнуешься с райдерами за районы города
— Рейтинг, война за квадратные метры
— Если через твою территорию идёт реклама — забираешь процент с бюджета. Катаешься и зарабатываешь.

Как начать: открыл бота → залил GPX-трек → твоя территория на карте.

Приводи друзей — бонусные захваты. Забирай районы, пока их не разобрали.

🔗 t.me/vel_io_bot"""

CHATS = [
    "velomoscow",
    "bikelove",
    "roadbikechat",
    "spbcycling",
    "krdvelo",
    "nnvelo",
    "rndvelo",
    "ekb_cycling",
    # add more
]


def load_log() -> set:
    try:
        with open("mailer_log.json") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_log(done: set):
    with open("mailer_log.json", "w") as f:
        json.dump(list(done), f, indent=2)


async def main():
    if not API_ID or not API_HASH:
        print("❌ Укажи API_ID и API_HASH из https://my.telegram.org")
        print("   API_ID=12345 API_HASH=abcdef python mass_mailer.py")
        sys.exit(1)

    client = TelegramClient(SESSION, int(API_ID), API_HASH)
    await client.start()
    me = await client.get_me()
    logger.info("Залогинен как %s", me.username or me.phone)

    done = load_log()
    remaining = [c for c in CHATS if c not in done]
    logger.info("Всего чатов: %d, уже отправлено: %d, осталось: %d",
                len(CHATS), len(done), len(remaining))

    if not remaining:
        logger.info("Всё уже разослано. Удали mailer_log.json чтобы начать заново.")
        return

    for i, chat in enumerate(remaining, 1):
        try:
            entity = await client.get_entity(chat)
            await client.send_message(entity, MESSAGE)
            done.add(chat)
            save_log(done)
            logger.info("[%d/%d] ✅ %s", i, len(remaining), chat)
        except ValueError:
            logger.warning("[%d/%d] ❌ %s — не найден", i, len(remaining), chat)
        except ChatWriteForbiddenError:
            logger.warning("[%d/%d] ❌ %s — нет прав писать", i, len(remaining), chat)
        except FloodWaitError as e:
            wait = e.seconds + 60
            logger.warning("Flood wait %d сек, жду...", wait)
            await asyncio.sleep(wait)
            # retry once
            try:
                entity = await client.get_entity(chat)
                await client.send_message(entity, MESSAGE)
                done.add(chat)
                save_log(done)
                logger.info("[%d/%d] ✅ %s (after flood)", i, len(remaining), chat)
            except Exception as e2:
                logger.warning("[%d/%d] ❌ %s — %s", i, len(remaining), chat, e2)
        except Exception as e:
            logger.warning("[%d/%d] ❌ %s — %s", i, len(remaining), chat, e)

        if i < len(remaining):
            delay = random.randint(MIN_DELAY, MAX_DELAY)
            logger.info("Жду %d сек...", delay)
            await asyncio.sleep(delay)

    logger.info("Готово! Отправлено в %d чатов.", len(done))


if __name__ == "__main__":
    asyncio.run(main())
