import json
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import types
from DataBase import *
from loader import *
from Log import *
from loader import *

chat_languages = {}
reply_to_messages = {}
languages = ["ru", "ua", "by", "en"]
translations = {}
default_language = "ru"
LANGUAGES_CODES = {
    "Українська": "ua",
    "Русский": "ru",
    "English": "en",
    "Беларуская": "by",
}
language_flags = {
    "ua": "🇺🇦",
    "ru": "🇷🇺",
    "en": "🇺🇸",
    "by": "🇧🇾",
}


async def delete_message_in_time(chat_id, message_id, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_message(chat_id, message_id)
        logging.info(f"Повідомлення з ID {message_id} було успішно видалено.")
    except Exception as e:
        logging.error(
            f"Помилка при видаленні повідомлення з ID {message_id}.", exc_info=True
        )


translations_cache = {}


def load_translations(lang):
    code = LANGUAGES_CODES.get(lang, lang)
    try:
        with open(BASE_DIR / f"{code}.json", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def translate_text(language, text_key):
    code = LANGUAGES_CODES.get(language, language)
    return translations.get(code, {}).get(
        text_key, translations.get("ru", {}).get(text_key, text_key)
    )


LANGUAGE_NAMES = {
    "ua": "Українська",
    "en": "English",
    "ru": "Русский",
    "by": "Беларуская",
}

for lang_name in LANGUAGES_CODES:
    translations[LANGUAGES_CODES[lang_name]] = load_translations(lang_name)


@dp.message_handler(commands=["language"])
async def set_language_command(message: types.Message):
    try:
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        logging.info(f"Current language for chat {chat_id}: {language}")
        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )

        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}"
        )
        logging.info(
            f"Current language: {language}, Available languages: {LANGUAGE_NAMES}"
        )

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🇺🇦 Українська 🇺🇦", callback_data="ua"),
            InlineKeyboardButton("🇬🇧 English 🇬🇧", callback_data="en"),
            InlineKeyboardButton("🇷🇺 Русский 🇷🇺", callback_data="ru"),
            InlineKeyboardButton("🇧🇾 Беларуская 🇧🇾", callback_data="by"),
        )

        translated_lan_text = translate_text(language, "Selected:")
        new_language = get_chat_language(chat_id)
        logging.info(f"New language for chat {chat_id}: {new_language}")
        logging.info(f"LANGUAGES_CODES: {LANGUAGES_CODES}")
        logging.info(f"new_language: {new_language}")

        if new_language in LANGUAGES_CODES.values():
            lang_code = new_language
            language_name = LANGUAGE_NAMES[lang_code]
        else:
            lang_code = LANGUAGES_CODES.get(new_language, "ru")
            language_name = LANGUAGE_NAMES[lang_code]
        await message.reply(
            f"{translated_lan_text} {language_name}", reply_markup=markup
        )
        # Збереження інформації про повідомлення користувача з командою /language
        reply_to_messages[message.chat.id] = {
            "message_id": message.message_id,
            "user_id": message.from_user.id,
        }
    except Exception as e:
        logging.error("Помилка функції Language", exc_info=True)


@dp.callback_query_handler(lambda query: query.data in LANGUAGES_CODES.values())
async def process_language_selection(query: types.CallbackQuery):
    try:
        chat_id = query.message.chat.id
        language = get_chat_language(chat_id)
        user_id = query.from_user.id
        language = query.data.replace("lang_", "")

        if query.message.chat.type != "private" and not await is_admin(
            chat_id, user_id
        ):
            await query.answer(
                "Менять язык группы может только администратор.", show_alert=True
            )
            return
        # Перевірка чи є користувач тим, хто викликав команду
        prev_message_info = reply_to_messages.get(chat_id)
        if not prev_message_info or prev_message_info["user_id"] != user_id:
            warning_text = translate_text(
                get_chat_language(chat_id), "This button is not for you!"
            )
            await bot.answer_callback_query(query.id, text=warning_text)
            return

        chat_languages[chat_id] = language
        logging.info(f"Set language for chat {chat_id} to: {language}")
        # Якщо language вже є кодом мови, то використовуємо його напряму, інакше - шукаємо код у LANGUAGES_CODES
        lang_code = (
            language
            if language in LANGUAGES_CODES.values()
            else LANGUAGES_CODES.get(language, "ru")
        )

        set_chat_language(chat_id, lang_code)

        translated_language_text = translate_text(language, "language_changed")
        language_name_in_current_language = LANGUAGE_NAMES[language]

        language_flag = language_flags.get(language, "")
        response_text = (
            translated_language_text.format(LANGUAGE_NAMES[language])
            + " "
            + language_flag
        )
        await bot.send_message(
            chat_id, response_text, reply_to_message_id=prev_message_info["message_id"]
        )
        # Чистимо після себе
        await query.answer()
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.delete()
        if chat_id in reply_to_messages:
            del reply_to_messages[chat_id]
    except Exception as e:
        logging.error("Помилка функції Language_Codes", exc_info=True)


# Обробник вибору мови чату


# Функція для отримання обраної мови чату
def get_chat_language(chat_id):
    from DataBase import get_chat_language as lookup

    return lookup(chat_id)


def get_user_language(user_id):
    from DataBase import get_user_language as lookup

    return lookup(user_id)


def get_language(context: types.Message or types.CallbackQuery) -> str:
    if isinstance(context, types.Message):
        if context.chat.type == "private":  # Якщо це приватне повідомлення
            return get_user_language(context.from_user.id)
        else:
            return get_chat_language(context.chat.id)
    elif isinstance(context, types.CallbackQuery):
        if context.message.chat.type == "private":
            return get_user_language(context.from_user.id)
        else:
            return get_chat_language(context.message.chat.id)
    return default_language  # якщо ми не змогли визначити контекст


def translate_time_remaining(time, language):
    minutes, seconds = divmod(time.seconds, 60)

    # Ініціалізація змінних за замовчуванням:
    minute_text = f"{minutes} минут"
    second_text = f"{seconds} секунд"

    if language == "ua":
        minute_text = pluralize_uk(minutes, ["хвилина", "хвилини", "хвилин"])
        second_text = pluralize_uk(seconds, ["секунда", "секунди", "секунд"])
    elif language == "en":
        minute_text = pluralize_en(minutes, "minute", "minutes")
        second_text = pluralize_en(seconds, "second", "seconds")
    elif language == "by":
        minute_text = pluralize_be(minutes, ["хвіліна", "хвіліны", "хвілін"])
        second_text = pluralize_be(seconds, ["секунда", "секунды", "секунд"])
    elif language == "ru":
        minute_text = pluralize_ru(minutes, ["минута", "минуты", "минут"])
        second_text = pluralize_ru(seconds, ["секунда", "секунды", "секунд"])

    logging.info(
        f"Language: {language}, Minutes: {minutes}, Seconds: {seconds}, Minute Text: {minute_text}, Second Text: {second_text}"
    )

    return f"{translate_text(language, 'Залишилось')} {minute_text} {second_text}"


def format_time(hours, minutes, language="en"):
    if language not in ("ru", "ua", "by", "en"):
        language = "ru"
    if language == "ua":
        # Українська
        hour_word = (
            "година"
            if hours in [1, 21]
            else "години"
            if hours in [2, 3, 4, 22, 23]
            else "годин"
        )
        minute_word = (
            "хвилина"
            if minutes % 10 == 1 and minutes != 11
            else "хвилини"
            if 2 <= minutes % 10 <= 4 and (minutes < 10 or minutes > 20)
            else "хвилин"
        )
    elif language == "en":
        # Англійська
        hour_word = "hour" if hours == 1 else "hours"
        minute_word = "minute" if minutes == 1 else "minutes"
    elif language == "ru":
        # Російська
        hour_word = (
            "час"
            if hours % 10 == 1 and hours != 11
            else "часа"
            if 2 <= hours % 10 <= 4 and (hours < 10 or hours > 20)
            else "часов"
        )
        minute_word = (
            "минута"
            if minutes % 10 == 1 and minutes != 11
            else "минуты"
            if 2 <= minutes % 10 <= 4 and (minutes < 10 or minutes > 20)
            else "минут"
        )
    elif language == "by":
        # Білоруська
        hour_word = (
            "гадзіна"
            if hours % 10 == 1 and hours != 11
            else "гадзіны"
            if 2 <= hours % 10 <= 4 and (hours < 10 or hours > 20)
            else "гадзін"
        )
        minute_word = (
            "хвіліна"
            if minutes % 10 == 1 and minutes != 11
            else "хвіліны"
            if 2 <= minutes % 10 <= 4 and (minutes < 10 or minutes > 20)
            else "хвілін"
        )

    return f"{hours} {hour_word} {minutes} {minute_word}"


def get_teeth_ending(count, language="ru"):
    if language == "ru":  # Russian
        if count == 1:
            return "зуб"
        elif 1 < count < 5:
            return "зуба"
        else:
            return "зубов"

    elif language in ("be", "by"):  # Belarusian
        if count == 1:
            return "зуб"
        elif 1 < count < 5:
            return "зубы"
        else:
            return "зубоў"

    elif language == "en":  # English
        if count == 1:
            return "tooth"
        else:
            return "teeth"

    elif language in ("uk", "ua"):  # Ukrainian
        if count == 1:
            return "зуб"
        elif 1 < count < 5:
            return "зуби"
        else:
            return "зубів"


def rank_to_string(rank, language):
    rank_names = {
        0: translate_text(language, "Немає рангу"),
        1: translate_text(language, "Однохвостий"),
        2: translate_text(language, "Двохвостий"),
        3: translate_text(language, "Трьохвостий"),
        4: translate_text(language, "Чотирьохвостий"),
        5: translate_text(language, "Пятихвостий"),
        6: translate_text(language, "Шестихвостий"),
        7: translate_text(language, "Семихвостий"),
        8: translate_text(language, "Восьмихвостий"),
        9: translate_text(language, "Девятихвостий"),
        10: translate_text(language, "Десятихвостий"),
    }
    return rank_names.get(rank, translate_text(language, "Невідомий ранг"))


async def handle_tail_change(message, tail_size, user_id):
    chat_id = message.chat.id
    language = get_chat_language(chat_id)  # Додаємо цю строку для отримання мови чату
    new_rank = update_rank_based_on_tail_size(tail_size, user_id)

    if new_rank is not None:
        new_rank_string = rank_to_string(
            new_rank, language
        )  # Передаємо мову як аргумент
        nickname_or_name = get_user_nickname_or_name(user_id)
        translated_message = translate_text(
            language, "{} ваш ранг змінився! Тепер ви - {}!"
        ).format(nickname_or_name, new_rank_string)
        await message.reply(translated_message)


def check_rank_and_send_message(user_id, total_tail_growth, chat_id):
    old_rank = get_user_rank(user_id)
    rank = update_rank_based_on_tail_size(total_tail_growth, user_id)
    return (
        rank_to_string(rank, get_chat_language(chat_id))
        if rank is not None and rank > old_rank
        else None
    )
