"""Два слоя монетизации: собственные рекламные объявления + справка по официальной монетизации Telegram.
Совместимо с aiogram 2.25.x. Собственные объявления хранятся отдельно в ads.sqlite3.
"""

import asyncio
import os
import uuid
from contextlib import contextmanager
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import YOUR_USER_ID
from loader import bot, dp

DB_PATH = Path(
    os.getenv("ADS_DB_PATH", str(Path(__file__).with_name("ads.sqlite3")))
).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
AD_INTERVAL_HOURS = int(os.getenv("AD_INTERVAL_HOURS", "24"))
if AD_INTERVAL_HOURS < 1:
    raise ValueError("AD_INTERVAL_HOURS must be positive")
logger = logging.getLogger(__name__)


@contextmanager
def _connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ad_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                url TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                impressions INTEGER NOT NULL DEFAULT 0,
                clicks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ad_user_log (
                user_id INTEGER PRIMARY KEY,
                ad_id INTEGER NOT NULL,
                last_shown_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ad_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT OR IGNORE INTO ad_settings(key, value) VALUES ('enabled', '1')"
        )

        conn.execute("""CREATE TABLE IF NOT EXISTS ad_claims (
            user_id INTEGER PRIMARY KEY, token TEXT NOT NULL, expires_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ad_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ad_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
            clicked INTEGER NOT NULL DEFAULT 0, shown_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id,message_id))""")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ad_deliveries_ad ON ad_deliveries(ad_id)"
        )


_init_db()


def _is_admin(user_id):
    return bool(user_id and user_id in YOUR_USER_ID)


def _ads_enabled():
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM ad_settings WHERE key='enabled'"
        ).fetchone()
        return bool(row and row["value"] == "1")


def _set_ads_enabled(enabled):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO ad_settings(key, value) VALUES ('enabled', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("1" if enabled else "0",),
        )


def _safe_url(url):
    if not url:
        return None
    url = url.strip()
    parsed = urlparse(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or any(ch.isspace() for ch in url)
    ):
        raise ValueError("Ссылка должна начинаться с https:// или http://")
    return url


def _format_ad(row):
    status = "🟢 активна" if row["active"] else "⚪ выключена"
    link = row["url"] or "нет"
    return (
        f"ID: {row['id']} — {row['title']}\n"
        f"Статус: {status}\n"
        f"Показы: {row['impressions']} | нажатия на кнопку: {row['clicks']}\n"
        f"Ссылка: {link}"
    )


def _ad_text(title, body):
    text = f"📣 Реклама\n\n{title}\n\n{body}"
    if not title.strip() or not body.strip():
        raise ValueError("Название и текст обязательны.")
    if len(text.encode("utf-16-le")) // 2 > 4096:
        raise ValueError(
            "Объявление слишком длинное: максимум 4096 символов с заголовком."
        )
    return text


async def _reply_chunks(message, text):
    # A conservative size also leaves room for astral characters (emoji).
    for start in range(0, len(text), 1800):
        await message.reply(
            text[start : start + 1800], parse_mode=None, disable_web_page_preview=True
        )


async def maybe_send_ad(message: types.Message):
    if (
        not message.from_user
        or message.from_user.is_bot
        or message.chat.type != "private"
    ):
        return
    command = (
        (message.text or "").split(maxsplit=1)[0].split("@")[0] if message.text else ""
    )
    if command.startswith(("/ad_", "/ads_")) or command == "/telegram_ads_info":
        return
    user_id = message.from_user.id
    if await dp.current_state(chat=message.chat.id, user=user_id).get_state():
        return
    token = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        enabled = conn.execute(
            "SELECT value FROM ad_settings WHERE key='enabled'"
        ).fetchone()
        if not enabled or enabled["value"] != "1":
            return
        recent = conn.execute(
            "SELECT 1 FROM ad_user_log WHERE user_id=? AND last_shown_at>datetime('now',?)",
            (user_id, f"-{AD_INTERVAL_HOURS} hours"),
        ).fetchone()
        pending = conn.execute(
            "SELECT 1 FROM ad_claims WHERE user_id=? AND expires_at>datetime('now')",
            (user_id,),
        ).fetchone()
        if recent or pending:
            return
        ad = conn.execute(
            "SELECT * FROM ad_campaigns WHERE active=1 ORDER BY impressions ASC,RANDOM() LIMIT 1"
        ).fetchone()
        if not ad:
            return
        text = _ad_text(ad["title"], ad["body"])
        conn.execute(
            "INSERT INTO ad_claims(user_id,token,expires_at) VALUES(?,?,datetime('now','+5 minutes')) ON CONFLICT(user_id) DO UPDATE SET token=excluded.token,expires_at=excluded.expires_at",
            (user_id, token),
        )
    try:
        keyboard = None
        if ad["url"]:
            _safe_url(ad["url"])
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Подробнее", callback_data=f"adclick:{ad['id']}")
            )
        delivered = await bot.send_message(
            message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode=None,
            disable_web_page_preview=True,
        )
        # Successful Bot API response is required to record an impression/cooldown.
        with _connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE ad_campaigns SET impressions=impressions+1 WHERE id=?",
                (ad["id"],),
            )
            conn.execute(
                "INSERT INTO ad_user_log(user_id,ad_id,last_shown_at) VALUES(?,?,datetime('now')) ON CONFLICT(user_id) DO UPDATE SET ad_id=excluded.ad_id,last_shown_at=excluded.last_shown_at",
                (user_id, ad["id"]),
            )
            conn.execute(
                "INSERT INTO ad_deliveries(ad_id,user_id,chat_id,message_id) VALUES(?,?,?,?)",
                (ad["id"], user_id, message.chat.id, delivered.message_id),
            )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning(
            "Не удалось отправить или записать рекламу для пользователя %s", user_id
        )
    finally:
        with _connect() as conn:
            conn.execute(
                "DELETE FROM ad_claims WHERE user_id=? AND token=?", (user_id, token)
            )


class AdMiddleware(BaseMiddleware):
    async def on_post_process_message(
        self, message: types.Message, results, data: dict
    ):
        try:
            await maybe_send_ad(message)
        except Exception:
            logger.warning("Ошибка рекламного middleware", exc_info=True)


dp.middleware.setup(AdMiddleware())


@dp.callback_query_handler(
    lambda c: c.data and re.fullmatch(r"adclick:\d+", c.data), state="*"
)
async def ad_click_callback(callback: types.CallbackQuery):
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Объявление недоступно.", show_alert=True)
        return
    ad_id = int(callback.data.split(":", 1)[1])
    with _connect() as conn:
        ad = conn.execute(
            "SELECT * FROM ad_campaigns WHERE id=? AND active=1", (ad_id,)
        ).fetchone()
        delivery = conn.execute(
            "SELECT id FROM ad_deliveries WHERE ad_id=? AND user_id=? AND chat_id=? AND message_id=?",
            (
                ad_id,
                callback.from_user.id,
                callback.message.chat.id,
                callback.message.message_id,
            ),
        ).fetchone()
    if not ad or not ad["url"] or not delivery:
        await callback.answer("Это объявление больше недоступно.", show_alert=True)
        return
    await callback.answer("Ссылка рекламодателя")
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Перейти по ссылке", url=_safe_url(ad["url"]))
    )
    await callback.message.answer(
        ad["title"] + "\nСсылка рекламодателя:", reply_markup=keyboard, parse_mode=None
    )
    with _connect() as conn:
        changed = conn.execute(
            "UPDATE ad_deliveries SET clicked=1 WHERE id=? AND clicked=0",
            (delivery["id"],),
        ).rowcount
        if changed:
            conn.execute("UPDATE ad_campaigns SET clicks=clicks+1 WHERE id=?", (ad_id,))


@dp.message_handler(commands=["ad_add"], state="*")
async def ad_add_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    args = message.get_args().strip()
    parts = [part.strip() for part in args.split("|", 2)]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        await message.reply(
            "Формат:\n/ad_add Название | Текст рекламы | https://example.com\n"
            "Ссылка необязательна, но без неё не будет кнопки перехода."
        )
        return
    title, body = parts[0], parts[1]
    try:
        _ad_text(title, body)
        url = _safe_url(parts[2]) if len(parts) == 3 and parts[2] else None
    except ValueError as exc:
        await message.reply(str(exc))
        return
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO ad_campaigns(title, body, url, active) VALUES (?, ?, ?, 1)",
            (title, body, url),
        )
        ad_id = cur.lastrowid
    await message.reply(f"✅ Объявление добавлено. ID: {ad_id}. Показы включены.")


@dp.message_handler(commands=["ad_list"], state="*")
async def ad_list_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ad_campaigns ORDER BY id DESC LIMIT 50"
        ).fetchall()
    if not rows:
        await message.reply(
            "Объявлений пока нет. Добавить: /ad_add Название | Текст | https://example.com"
        )
        return
    await _reply_chunks(message, "\n\n".join(_format_ad(row) for row in rows))


@dp.message_handler(commands=["ad_delete"], state="*")
async def ad_delete_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("Формат: /ad_delete ID")
        return
    with _connect() as conn:
        conn.execute("DELETE FROM ad_deliveries WHERE ad_id=?", (int(args),))
        cur = conn.execute("DELETE FROM ad_campaigns WHERE id=?", (int(args),))
    await message.reply(
        "🗑 Объявление удалено." if cur.rowcount else "Объявление с таким ID не найдено."
    )


async def _set_ad_active(message: types.Message, active: bool):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("Формат: /ad_on ID" if active else "Формат: /ad_off ID")
        return
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE ad_campaigns SET active=? WHERE id=?", (int(active), int(args))
        )
    if cur.rowcount:
        await message.reply(
            "🟢 Объявление включено." if active else "⚪ Объявление выключено."
        )
    else:
        await message.reply("Объявление с таким ID не найдено.")


@dp.message_handler(commands=["ad_on"], state="*")
async def ad_on_command(message: types.Message):
    await _set_ad_active(message, True)


@dp.message_handler(commands=["ad_off"], state="*")
async def ad_off_command(message: types.Message):
    await _set_ad_active(message, False)


@dp.message_handler(commands=["ad_stats"], state="*")
async def ad_stats_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    args = message.get_args().strip()
    with _connect() as conn:
        if args:
            if not args.isdigit():
                await message.reply("Формат: /ad_stats или /ad_stats ID")
                return
            rows = conn.execute(
                "SELECT * FROM ad_campaigns WHERE id=?", (int(args),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ad_campaigns ORDER BY id DESC"
            ).fetchall()
    if not rows:
        await message.reply("Статистика пуста или объявление не найдено.")
        return
    total_impressions = sum(row["impressions"] for row in rows)
    total_clicks = sum(row["clicks"] for row in rows)
    result = "📊 Статистика рекламы\n\n" + "\n\n".join(_format_ad(row) for row in rows)
    if not args:
        result += (
            f"\n\nВсего показов: {total_impressions}\nНажатий на кнопку: {total_clicks}"
        )
    await _reply_chunks(message, result)


@dp.message_handler(commands=["ads_pause"], state="*")
async def ads_pause_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    _set_ads_enabled(False)
    await message.reply("⏸ Все собственные рекламные показы приостановлены.")


@dp.message_handler(commands=["ads_resume"], state="*")
async def ads_resume_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    _set_ads_enabled(True)
    await message.reply("▶️ Собственные рекламные показы снова включены.")


@dp.message_handler(commands=["telegram_ads_info"], state="*")
async def telegram_ads_info_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    await message.reply(
        "📘 Официальная монетизация Telegram\n\n"
        "Она не управляется командами /ad_add и /ad_delete: Telegram сам размещает официальные объявления, "
        "а доступность и начисления определяются платформой.\n\n"
        "1. Открой профиль своего бота и раздел Balance/Баланс или Monetization/Монетизация, если он доступен.\n"
        "2. Проверь доступность рекламной монетизации и статистику доходов.\n"
        "3. Для актуальных условий используй официальную документацию: https://core.telegram.org/api/revenue\n\n"
        "Команды этого модуля управляют только собственной рекламой, которую бот отправляет пользователям."
    )


@dp.message_handler(commands=["ads_help"], state="*")
async def ads_help_command(message: types.Message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    await message.reply(
        "Команды управления собственной рекламой:\n"
        "/ad_add Название | Текст | https://example.com — добавить\n"
        "/ad_list — список объявлений и статистика\n"
        "/ad_test ID — тестовый показ без статистики\n"
        "/ad_edit ID | Название | Текст | URL — изменить\n"
        "/ad_delete ID — удалить\n"
        "/ad_on ID — включить объявление\n"
        "/ad_off ID — выключить объявление\n"
        "/ad_stats — общая статистика\n"
        "/ad_stats ID — статистика одного объявления\n"
        "/ads_pause — приостановить все показы\n"
        "/ads_resume — возобновить показы\n"
        "/telegram_ads_info — справка по официальной монетизации Telegram\n\n"
        f"Частота: не чаще одного собственного объявления на пользователя за {AD_INTERVAL_HOURS} часов, только в личном чате."
    )


@dp.message_handler(commands=["ad_test"], state="*")
async def ad_test_command(message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    if message.chat.type != "private":
        await message.reply("Проверяйте объявления в личном чате с ботом.")
        return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.reply("Формат: /ad_test ID")
        return
    with _connect() as conn:
        ad = conn.execute(
            "SELECT * FROM ad_campaigns WHERE id=?", (int(args),)
        ).fetchone()
    if not ad:
        await message.reply("Объявление не найдено.")
        return
    keyboard = (
        InlineKeyboardMarkup().add(
            InlineKeyboardButton("Перейти по ссылке", url=_safe_url(ad["url"]))
        )
        if ad["url"]
        else None
    )
    await message.answer(
        _ad_text(ad["title"], ad["body"]), reply_markup=keyboard, parse_mode=None
    )
    await message.reply("Тестовый показ: статистика и суточный лимит не изменены.")


@dp.message_handler(commands=["ad_edit"], state="*")
async def ad_edit_command(message):
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.reply("Команда доступна только администратору.")
        return
    parts = [part.strip() for part in message.get_args().split("|", 3)]
    if len(parts) < 3 or not parts[0].isdigit():
        await message.reply(
            "Формат: /ad_edit ID | Название | Текст | https://example.com (пустая ссылка удаляет кнопку)"
        )
        return
    try:
        _ad_text(parts[1], parts[2])
        url = _safe_url(parts[3]) if len(parts) == 4 and parts[3] else None
    except ValueError as error:
        await message.reply(str(error))
        return
    with _connect() as conn:
        result = conn.execute(
            "UPDATE ad_campaigns SET title=?,body=?,url=? WHERE id=?",
            (parts[1], parts[2], url, int(parts[0])),
        )
    await message.reply(
        "Объявление обновлено." if result.rowcount else "Объявление не найдено."
    )
