from Log import *
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode
from aiogram.dispatcher import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import filters
from aiohttp import ClientSession
import re
from io import BytesIO
import base64
import aiofiles
import itertools

import aiohttp
import pytz
import random
import aiogram
import os
import shutil
import json
import requests
from config import *
from DataBase import *

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

global last_messages
last_messages = {}
global last_teeth_gain_time
last_teeth_gain_time = {}
global daily_teeth_gain
daily_teeth_gain = {}


def is_admins(user_id):
    return user_id in YOUR_USER_ID


async def is_admin(chat_id, user_id):
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ["administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False


def time_left(user_id):
    last_used = last_used_time.get(user_id)
    if not last_used:
        return None

    next_use_time = last_used + timedelta(hours=1)
    delta = next_use_time - datetime.now()

    if delta.total_seconds() <= 0:
        return 0

    return int(delta.total_seconds() // 60)


user_id_to_reset = 1  # Замініть на актуальний ID користувача
scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")
logging.basicConfig(level=logging.INFO)  # Додано логування


async def backup_db_and_notify():
    path = backup_database()
    logging.info("Database backup completed")
    try:
        await bot.send_message(ADMIN_ID, f"Резервная копия базы: {path.name}")
    except aiogram.utils.exceptions.TelegramAPIError:
        logging.warning("Could not notify administrator about backup")


async def on_start(dispatcher):
    if not scheduler.running:
        scheduler.add_job(
            backup_db_and_notify,
            "cron",
            day=1,
            hour=0,
            minute=0,
            id="backup",
            replace_existing=True,
        )
        scheduler.add_job(
            clean_database,
            "cron",
            hour=3,
            minute=10,
            id="cleanup",
            replace_existing=True,
        )
        scheduler.start()
    logging.info("Бот запущен; планировщик включён")


async def on_shutdown(dispatcher):
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    conn.close()


load_last_used_times()


def pluralize_uk(num, forms):
    if num % 10 == 1 and num % 100 != 11:
        return f"{num} {forms[0]}"
    elif 2 <= num % 10 <= 4 and (num % 100 < 12 or num % 100 > 14):
        return f"{num} {forms[1]}"
    else:
        return f"{num} {forms[2]}"


def pluralize_ru(num, forms):
    if num % 10 == 1 and num % 100 != 11:
        return f"{num} {forms[0]}"
    elif 2 <= num % 10 <= 4 and (num % 100 < 12 or num % 100 > 14):
        return f"{num} {forms[1]}"
    else:
        return f"{num} {forms[2]}"


def pluralize_be(num, forms):
    if num % 10 == 1 and num % 100 != 11:
        return f"{num} {forms[0]}"
    elif 2 <= num % 10 <= 4 and (num % 100 < 12 or num % 100 > 14):
        return f"{num} {forms[1]}"
    else:
        return f"{num} {forms[2]}"


def pluralize_en(num, singular, plural):
    return f"{num} {singular if num == 1 else plural}"


def generate_random_num():
    return round(random.uniform(-4.5, 10), 1)


def get_user_display_name(user):
    user_nickname = get_user_nickname_or_name(user[0])  # Отримуємо нікнейм за user_id
    return user_nickname or user[1]


def round_tail_growth(tail_growth):
    return round(tail_growth, 1)


def format_timedelta(td):
    days, remainder = divmod(td.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    day_word = "день" if days == 1 else "дні" if 1 < days < 5 else "днів"
    return f"{int(days)} {day_word} {int(hours):02}:{int(minutes):02}:{int(seconds):02}"


# Встановіть час запуску, коли бот стартує
START_TIME = datetime.now()


def get_back_keyboard(user_id):
    inline_keyboard = InlineKeyboardMarkup(row_width=1)
    inline_btn_back = InlineKeyboardButton(
        "🔙", callback_data=f"back_to_selection:{user_id}"
    )
    inline_keyboard.add(inline_btn_back)
    return inline_keyboard


# Log rotation is handled by Log.py; no file-truncating background task.
def add_chat_id_for_user(user_id, chat_id):
    add_chat_id_to_user(user_id, chat_id)


def get_top1_chat_users(chat_id):
    # Запит до UserChats для отримання всіх користувачів цього чату
    users_in_chat = cursor.execute(
        "SELECT user_id FROM UserChats WHERE chat_id = ?", (chat_id,)
    ).fetchall()
    user_ids = [user[0] for user in users_in_chat]

    # Запит до Users для отримання інформації про кожного користувача
    top_users = []
    for user_id in user_ids:
        user_data = cursor.execute(
            "SELECT id, nickname, name, total_tail_growth FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user_data and user_data[3]:  # перевіряємо чи існує хвостик у користувача
            top_users.append(user_data)

    # Сортуємо список користувачів за довжиною хвостика
    top_users = sorted(top_users, key=lambda x: x[3], reverse=True)

    return top_users


async def bot_has_admin_rights(chat_id):
    try:
        bot_data = await bot.get_me()
        bot_id = bot_data.id
        member = await bot.get_chat_member(chat_id, bot_id)
        return member.status == "creator" or (
            member.status == "administrator" and member.can_delete_messages
        )
    except Exception as e:
        logging.error(
            f"Failed to check bot permissions in chat {chat_id}", exc_info=True
        )
        return False


async def schedule_message_deletion(chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for message_id in message_ids:
        try:
            logging.info(f"Attempting to delete message {message_id} in chat {chat_id}")
            await bot.delete_message(chat_id, message_id)
            logging.info(f"Successfully deleted message {message_id} in chat {chat_id}")
            if chat_id in last_messages:
                last_messages[chat_id] = [
                    (mid1, mid2)
                    for mid1, mid2 in last_messages[chat_id]
                    if mid1 != message_id and mid2 != message_id
                ]
        except Exception as e:
            logging.error(
                f"Failed to delete message {message_id} in chat {chat_id}",
                exc_info=True,
            )


def load_teeth(language):
    try:
        with open(BASE_DIR / "teeth.json", "r", encoding="utf-8") as file:
            data = json.load(file)

            # Отримуємо фрази для заданої мови, а якщо їх немає, то повертаємо порожній словник
            phrases_for_language = data.get(language, {})

            return phrases_for_language
    except Exception as e:
        print(f"Error loading phrases: {e}")
        return {}


def update_rank(tail_size_change, user_id):
    return update_rank_based_on_tail_size(tail_size_change, user_id)


def get_user_display_nickname(user):
    nickname = user[1] if user[1] and user[1].strip() != "" else "🦊"
    username = (
        user[2].strip() if isinstance(user[2], str) and user[2].strip() != "" else ""
    )  # додав альтернативу для випадків, коли username також відсутній

    return f"{nickname} ({username})"


async def clean_removed_users(chat_id):
    # Do not infer membership from other chats: a single-chat player is valid.
    update_all_chats_players_count()


async def clean_removed_chats():
    for chat in get_all_chats_from_db():
        chat_id = chat["chat_id"]
        if chat_id > 0:
            continue
        try:
            member = await bot.get_chat_member(chat_id, bot.id)
            if member.status in ("left", "kicked"):
                delete_chat_and_users_from_db(chat_id)
        except (
            aiogram.utils.exceptions.BotKicked,
            aiogram.utils.exceptions.ChatNotFound,
        ):
            delete_chat_and_users_from_db(chat_id)
        except aiogram.utils.exceptions.TelegramAPIError:
            # Transient errors or missing permissions never justify deleting data.
            logging.warning(
                "Membership check failed for chat %s; retaining data", chat_id
            )


async def clean_database():
    removed = cleanup_inactive_users(INACTIVE_USER_DAYS)
    logging.info("Inactive profiles removed: %s", len(removed))
    await clean_removed_chats()


async def get_fox_image():
    async with ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.get("https://randomfox.ca/floof/") as response:
            response.raise_for_status()
            return (await response.json()).get("image")


load_dotenv = os.getenv("predictions.json")

load_dotenv = os.getenv("tail_responses.json")
# with open('predictions.json', 'r', encoding='utf-8') as file:
#    predictions = json.load(file)


async def get_image(url):
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=20)
    ) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            if data.get("url"):
                return data["url"]
            if data.get("image"):
                return data["image"]
            results = data.get("results") or []
            return results[0].get("url") if results else None


def from_nekos_best(kinds):
    return {type: f"https://nekos.best/api/v2/{type}" for type in kinds}


def from_hmtai(mode, kinds):
    return {
        type
        if isinstance(type, str)
        else type[
            0
        ]: f"https://hmtai.hatsunia.cfd/{mode}/{type if isinstance(type, str) else type[1]}"
        for type in kinds
    }


sources = {
    "sfw": {
        **from_nekos_best(["waifu", "neko", "kitsune"]),
        **from_hmtai(
            "sfw",
            [
                "tea",
                "bonk",
                "pat",
                "kiss",
                "feed",
                "hug",
                "cuddle",
                "cry",
                "cringe",
                "nom",
                "smile",
                "lick",
                "bite",
                "dance",
                "boop",
                "sleep",
                "kill",
                "tickle",
                "nosebleed",
                "depression",
                ("wolf", "wolf_arts"),
                ("coffee", "coffee_arts"),
            ],
        ),
        "kitsune": "https://nekos.best/api/v2/kitsune",
        "fox_girl": "https://nekos.life/api/v2/img/fox_girl",
        "fox": "https://randomfox.ca/floof/",
    }
}


class TailExchange(StatesGroup):
    waiting_for_teeth_count = State()


from aiogram.dispatcher.middlewares import BaseMiddleware


class ActivityMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message, data):
        if message.text and message.text.startswith("/"):
            head, *rest = message.text.split(maxsplit=1)
            if "@" in head:
                command, target = head.split("@", 1)
                me = await bot.get_me()
                if target.lower() != (me.username or "").lower():
                    from aiogram.dispatcher.handler import CancelHandler

                    raise CancelHandler()
                message.text = command + (" " + rest[0] if rest else "")
        user = message.from_user
        if (
            user
            and not user.is_bot
            and not message.left_chat_member
            and not message.new_chat_members
        ):
            record_activity(user.id, user.full_name, message.chat.id)
        for joined in message.new_chat_members or []:
            if not joined.is_bot:
                record_activity(joined.id, joined.full_name, message.chat.id)
        if message.left_chat_member:
            remove_user_from_chat(message.left_chat_member.id, message.chat.id)
        if message.migrate_to_chat_id:
            migrate_chat(message.chat.id, message.migrate_to_chat_id)

    async def on_pre_process_callback_query(self, callback, data):
        if callback.from_user and not callback.from_user.is_bot:
            record_activity(callback.from_user.id, callback.from_user.full_name)


dp.middleware.setup(ActivityMiddleware())


@dp.my_chat_member_handler()
async def bot_membership_update(update):
    if update.new_chat_member.status in ("left", "kicked"):
        delete_chat_and_users_from_db(update.chat.id)
    else:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO Chats(chat_id) VALUES(?)", (update.chat.id,)
            )


@dp.chat_member_handler()
async def player_membership_update(update):
    member = update.new_chat_member
    if member.user.is_bot:
        return
    if member.status in ("left", "kicked") or (
        member.status == "restricted" and not member.is_member
    ):
        remove_user_from_chat(member.user.id, update.chat.id)
    else:
        record_activity(member.user.id, member.user.full_name, update.chat.id)
