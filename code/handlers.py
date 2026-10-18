from aiogram import types
import html
import os
from datetime import datetime, timedelta
import psutil
from aiogram.utils.exceptions import MessageToDeleteNotFound, MessageCantBeDeleted
import aiogram
from language import *
from Log import *
from loader import *

broadcast_message = None


@dp.message_handler(commands=["start"], chat_type=types.ChatType.PRIVATE)
async def command_start(message: types.Message):
    chat_id = message.chat.id
    language = get_chat_language(chat_id)
    chat_languages[chat_id] = language
    chat_title = message.chat.title or message.chat.username or message.chat.first_name

    try:
        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' використав команду: {message.text}"
        )
    except Exception as e:
        print(f"Error logging the action: {e}")

    hand_down_smiley = "\U0001f447"
    finger_smiley = "\U0001f449"
    left_arrow_smiley = "\U0001f448"

    # Відправляємо повідомлення в приватному чаті
    text = (
        f"Привет, {message.from_user.first_name}! Лисёнок— бот-для выращивання хвостика только для групп (чатов)\n\n"
        "Раз в час игрок может ввести команду /tail, чтобы выростить хвостик\n"
        "Мои команды — /help\n\n"
        f"Канал лисёнка: @FoxyTail_official\n"
        f"Если у вас остались вопросы или вы хотите предложить идею, пишите нам. @Foxy_chati \n\n"
        f"Нажми на кнопку ниже чтобы добавить лисёнка в чат: {hand_down_smiley}"
    )

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            f"{finger_smiley} Добавить бота в группу (чат) {left_arrow_smiley}",
            url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true",
        )
    )

    await message.answer(text, reply_markup=markup)


REPLY_TO_JOIN_LEAVE = {}


@dp.message_handler(
    lambda message: message.text in ["/toggle", "!приветствие", "!привітання"]
)
async def toggle_join_leave_reply(message: types.Message):
    try:
        global REPLY_TO_JOIN_LEAVE
        chat_id = message.chat.id
        language = get_chat_language(chat_id)

        if not await is_admin(message.chat.id, message.from_user.id):
            await message.reply(
                f"{translate_text(language, 'Ви не є адміністратором цього чату.')}"
            )
            return

        REPLY_TO_JOIN_LEAVE[chat_id] = not REPLY_TO_JOIN_LEAVE.get(chat_id, True)
        status = (
            translate_text(language, "enabled")
            if REPLY_TO_JOIN_LEAVE.get(chat_id, True)
            else translate_text(language, "disabled")
        )

        response_template = translate_text(
            language, "Відповідь на приєднання/вихід користувачів тепер {status}."
        )
        await message.reply(response_template.format(status=status))

    except Exception as e:
        logging.error("problem command Pryvit", exc_info=True)


@dp.message_handler(content_types=types.ContentType.NEW_CHAT_MEMBERS)
async def on_user_joined(message: types.Message):
    if not REPLY_TO_JOIN_LEAVE.get(message.chat.id, True):
        return

    chat_id = message.chat.id
    language = get_chat_language(chat_id)

    chat_title = message.chat.title or message.chat.username or message.chat.first_name

    # Логування кожного нового користувача
    for user in message.new_chat_members:
        try:
            logging.info(
                f"Користувач {user.full_name} {user.id} приєднався до чату '{chat_title}'."
            )
        except Exception as e:
            print(f"Error logging the action: {e}")

    # Створення посилань на нових користувачів
    new_users = ", ".join(
        [
            f"<a href='tg://user?id={user.id}'>{html.escape(user.username or user.full_name)}</a>"
            for user in message.new_chat_members
        ]
    )

    await message.reply(
        f"{translate_text(language, 'Ласкаво просимо,')} {new_users}!\n{translate_text(language, 'Надіємося, вам сподобається тут.')}",
        parse_mode="HTML",
    )


@dp.message_handler(content_types=types.ContentType.LEFT_CHAT_MEMBER)
async def on_user_left(message: types.Message):
    if not REPLY_TO_JOIN_LEAVE.get(message.chat.id, True):
        return
    chat_id = message.chat.id
    language = get_chat_language(chat_id)

    chat_title = message.chat.title or message.chat.username or message.chat.first_name

    # Логування користувача, який покинув чат
    try:
        logging.info(
            f"Користувач {message.left_chat_member.full_name} {message.left_chat_member.id} покинув чат '{chat_title}'."
        )
    except Exception as e:
        print(f"Error logging the action: {e}")

    # Отримання імені користувача, який покинув чат, і його ID
    left_user_name = (
        message.left_chat_member.username
        if message.left_chat_member.username
        else message.left_chat_member.full_name
    )
    left_user_id = message.left_chat_member.id

    # Створення лінку на користувача
    left_user_link = (
        f"<a href='tg://user?id={left_user_id}'>{html.escape(left_user_name)}</a>"
    )

    # Відправлення повідомлення
    await message.reply(
        f"{translate_text(language, 'покинув нас.')} {left_user_link} {translate_text(language, 'пака')}\n{translate_text(language, 'Сподіваємося, вам тут було комфортно.')}",
        parse_mode="HTML",
    )


def starts_with_tail_command(text):
    words = (text or "").lower().split()
    return bool(words and words[0].split("@")[0] in ("/tail", "!хвостик", "!растить"))


BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "tail_responses.json", "r", encoding="utf-8") as file:
    TAIL_RESPONSES = json.load(file)


def get_tail_response(change, language="ru"):
    for key, variants in TAIL_RESPONSES.items():
        try:
            if "to" in key:
                low, high = (float(value.strip()) for value in key.split("to", 1))
                matches = low <= change <= high
            else:
                matches = float(key) == change
        except ValueError:
            continue
        if matches:
            return (
                variants.get(language)
                or variants.get("ru")
                or "Изменение хвостика: {} см."
            )
    return "Изменение хвостика: {} см."


async def display_tail_growth(message, tail_growth, translated_text, teeth_message=""):
    user_id = message.from_user.id
    await message.reply(f"{get_user_nickname_or_name(user_id)}, {translated_text}")
    if teeth_message:
        await message.reply(f"{get_user_nickname_or_name(user_id)}, {teeth_message}")


def teeth_growth_random_phrase(teeth_gain, chat_id, language=None):
    # Якщо мову не передано як аргумент, отримуємо мову з чату
    if not language:
        language = get_chat_language(chat_id)
    # print(f"Using language: {language}")  # Логування використовуваної мови

    phrases = load_teeth(language)

    try:
        selected_phrase_list = []

        if teeth_gain == 1:
            selected_phrase_list = phrases.get("phrases_single", [])
        elif 1 < teeth_gain < 5:
            selected_phrase_list = phrases.get("phrases_multiple_2_4", [])
        else:
            selected_phrase_list = phrases.get("phrases_multiple_5_plus", [])

        if not selected_phrase_list:
            raise ValueError(
                f"No phrases found for teeth_gain: {teeth_gain} and language: {language}"
            )

        return random.choice(selected_phrase_list).format(teeth_gain=teeth_gain)

    except Exception as e:
        print(f"Error generating phrase: {e}")
        return "Error!"


@dp.message_handler(lambda message: starts_with_tail_command(message.text))
async def pump_tail_command(message: types.Message):
    user_id = message.from_user.id
    record_activity(user_id, message.from_user.full_name, message.chat.id)
    language = get_chat_language(message.chat.id)
    delta = generate_random_num()
    allowed, remaining, total = grow_tail(user_id, delta)
    if not allowed:
        await message.reply(
            f"{get_user_nickname_or_name(user_id)}, {translate_text(language, 'You can only pump your tail once an hour!')}\n{translate_time_remaining(remaining, language)}"
        )
        return
    new_rank = check_rank_and_send_message(user_id, total, message.chat.id)
    if new_rank:
        await message.answer(
            translate_text(language, "{} вітаю! Тепер ваш ранг - {}!").format(
                get_user_nickname_or_name(user_id), new_rank
            )
        )
    teeth_message = ""
    teeth = get_user_teeth(user_id)
    if teeth < 42 and random.random() < 0.10:
        gain = random.randint(1, min(3, 42 - teeth))
        add_or_remove_teeth(user_id, gain)
        teeth_message = teeth_growth_random_phrase(gain, message.chat.id)
    response = get_tail_response(delta, language).format(abs(delta))
    await display_tail_growth(message, delta, response, teeth_message)


def starts_with_top_command(text):
    if not text:
        return False
    lower_text = (text or "").lower()
    return (
        lower_text.startswith("/show")
        or lower_text.startswith("!топ")
        or lower_text.startswith("!топчик")
    )


@dp.message_handler(lambda message: starts_with_top_command(message.text))
async def show_top(message: types.Message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)

        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )

        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}"
        )

        chat_exists = cursor.execute(
            "SELECT 1 FROM UserChats WHERE chat_id = ?", (chat_id,)
        ).fetchone()

        # If not, insert it
        if not chat_exists:
            cursor.execute(
                "INSERT INTO Chats (chat_id, language) VALUES (?, ?)",
                (chat_id, language or ""),
            )

        # Now update the Users table
        cursor.execute(
            "INSERT OR IGNORE INTO Users (id, nickname, name) VALUES (?, ?, ?)",
            (user_id, message.from_user.username, message.from_user.full_name),
        )

        # Use your function to handle UserChats table
        add_chat_id_for_user(user_id, chat_id)
        conn.commit()
        inline_keyboard = InlineKeyboardMarkup(row_width=1)
        inline_btn_chat = InlineKeyboardButton(
            translate_text(language, "Найдовший хвостик чату"),
            callback_data=f"top_chat:{user_id}",
        )
        inline_btn_all_chats = InlineKeyboardButton(
            translate_text(language, "Найдовший хвостик серед користувачів"),
            callback_data=f"top_all_chats:{user_id}",
        )
        inline_btn_ranks = InlineKeyboardButton(
            translate_text(language, "Топ багатохвостиків"),
            callback_data=f"top_ranks:{user_id}",
        )
        inline_keyboard.add(inline_btn_chat, inline_btn_all_chats, inline_btn_ranks)

        response_text = translate_text(language, "В кого тут найдовший хвостик?:")
        response = await message.reply(response_text, reply_markup=inline_keyboard)
        if chat_id not in last_messages:
            last_messages[chat_id] = []
        last_messages[chat_id].append((message.message_id, response.message_id))

        # Поставити таймер на видалення цих повідомлень після 5 хвилин
        asyncio.create_task(
            schedule_message_deletion(
                chat_id, [message.message_id, response.message_id], 300
            )
        )  # 300 секунд 5 хвилин

        if not await bot_has_admin_rights(chat_id):
            logging.warning(
                f"Bot doesn't have admin rights in the chat '{message.chat.title}' with ID {chat_id}."
            )
            admin_rights_message_part1 = translate_text(
                language, "Для повноцінної роботи мені потрібні права адміністратора:"
            )
            admin_rights_message_part2 = translate_text(
                language, "· можливість видаляти повідомлення."
            )
            admin_rights_message = (
                f"{admin_rights_message_part1}\n{admin_rights_message_part2}"
            )
            await message.reply(admin_rights_message)
    except Exception as e:
        logging.error("Помилка фунції /top", exc_info=True)


@dp.callback_query_handler(lambda query: (query.data or "").startswith("top_"))
async def process_top_selection(query: types.CallbackQuery):
    try:
        command, user_id = query.data.split(":")
        user_id = int(user_id)

        if user_id != query.from_user.id:
            await bot.answer_callback_query(
                query.id,
                text=translate_text(
                    get_chat_language(query.message.chat.id),
                    "This button is not for you!",
                ),
            )
            return

        chat_id = query.message.chat.id
        language = get_chat_language(chat_id)
        translated_cm_text = translate_text(language, "cm")

        back_keyboard = get_back_keyboard(user_id)  # Додавання клавіатури "Назад"
        if command == "top_chat":
            top_chat_users = get_top_chat_users(chat_id)
            if top_chat_users:
                top_users_text = "\n".join(
                    [
                        f"{idx + 1}. {get_user_display_nickname(user)} - {round(user[3], 1)} {translated_cm_text}"
                        for idx, user in enumerate(top_chat_users)
                    ]
                )
                response_text = f"{translate_text(language, 'Найдовший хвостик чату:')}\n{top_users_text}"
            else:
                response_text = translate_text(
                    language, "На жаль, тут ще немає користувачів з хвостиками."
                )
        elif command == "top_all_chats":
            top_all_chats_users = get_top_all_chats_users()
            if top_all_chats_users:
                top_users_text = "\n".join(
                    [
                        f"{idx + 1}. {get_user_display_name(user)} - {round_tail_growth(user[2])} {translated_cm_text}"
                        for idx, user in enumerate(top_all_chats_users)
                    ]
                )
                response_text = f"{translate_text(language, 'Найдовший хвостик серед користувачів:')}\n{top_users_text}"
            else:
                response_text = translate_text(
                    language, "На жаль, ще немає чатів з хвостиками."
                )
        elif command == "top_ranks":
            top_ranks_users = get_top_ranks_users()

            if top_ranks_users:
                users_text = "\n".join(
                    [
                        f"{idx + 1}. {get_user_display_nickname(user)} - {rank_to_string(user[3], language)}"
                        for idx, user in enumerate(top_ranks_users)
                    ]
                )
                response_text = f"{translate_text(language, 'Найвищий ранг серед користувачів:')}\n{users_text}"
            else:
                response_text = translate_text(
                    language, "На жаль, ще немає користувачів з рангами."
                )

        await bot.edit_message_text(
            response_text, chat_id, query.message.message_id, reply_markup=back_keyboard
        )

        # Редагуємо поточне повідомлення з новою інформацією та кнопкою "Назад"
        await query.answer()

    except Exception as e:
        logging.error("Помилка виводу топу", exc_info=True)


@dp.callback_query_handler(
    lambda query: (query.data or "").startswith("back_to_selection")
)
async def back_to_selection(query: types.CallbackQuery):
    try:
        _, user_id = query.data.split(":")
        user_id = int(user_id)

        if user_id != query.from_user.id:
            await bot.answer_callback_query(
                query.id,
                text=translate_text(
                    get_chat_language(query.message.chat.id),
                    "This button is not for you!",
                ),
            )
            return

        chat_id = query.message.chat.id
        language = get_chat_language(chat_id)
        inline_keyboard = InlineKeyboardMarkup(row_width=1)
        inline_btn_chat = InlineKeyboardButton(
            translate_text(language, "Найдовший хвостик чату"),
            callback_data=f"top_chat:{user_id}",
        )
        inline_btn_all_chats = InlineKeyboardButton(
            translate_text(language, "Найдовший хвостик серед користувачів"),
            callback_data=f"top_all_chats:{user_id}",
        )
        inline_btn_ranks = InlineKeyboardButton(
            translate_text(language, "Топ багатохвостиків"),
            callback_data=f"top_ranks:{user_id}",
        )
        inline_keyboard.add(inline_btn_chat, inline_btn_all_chats, inline_btn_ranks)

        response_text = translate_text(language, "В кого тут найдовший хвостик?:")

        await query.answer()
        await bot.edit_message_text(
            response_text,
            chat_id,
            query.message.message_id,
            reply_markup=inline_keyboard,
        )  # Редагуємо поточне повідомлення

    except Exception as e:
        logging.error("Помилка при натисканні на кнопку 'Бек'", exc_info=True)


# ПРОФІЛЬ


def starts_with_prof_command(text):
    lower_text = (text or "").lower()
    return (
        lower_text.startswith("/prof")
        or lower_text.startswith("!профіль")
        or lower_text.startswith("!профиль")
    )


@dp.message_handler(lambda message: starts_with_prof_command(message.text))
async def prof(message: types.Message):
    try:
        user_id = message.from_user.id
        user_first_name = message.from_user.first_name
        user_username = message.from_user.username or ""
        user_nickname = get_user_nickname(user_id) or "🦊"
        user_tail_growth = get_tail_growth(user_id)
        rounded_tail_growth = round_tail_growth(user_tail_growth)
        user_teeth = get_user_teeth(user_id)
        chat_id = message.chat.id
        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )
        language = get_chat_language(chat_id)
        translated_cm_text = translate_text(language, "cm")
        user_rank_numeric = get_user_rank(user_id)
        user_rank_text = rank_to_string(user_rank_numeric, language)

        logging.info(f"Ваш ранг: {user_rank_text}")
        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}"
        )

        # Экранируем все переменные, которые могут содержать символы HTML
        response = (
            f"🌟 <b>{translate_text(language, 'Твоє імя:')}</b> {html.escape(user_first_name)}\n"
            f"🦊 <b>{translate_text(language, 'Твою лисичку звуть:')}</b> {html.escape(user_nickname)}\n"
            f"📏 <b>{translate_text(language, 'Довжина твого хвостика:')}</b> {rounded_tail_growth} {translated_cm_text}\n"
            f"🏆 <b>{translate_text(language, 'Ранг:')}</b> {html.escape(user_rank_text)}\n"
            f"🦷 <b>{translate_text(language, 'Кількість зубів:')}</b> {user_teeth}/42\n"
        )

        await message.reply(response, parse_mode="HTML")

    except Exception as e:
        logging.error("Problem open profile", exc_info=True)


def starts_with_help_command(text):
    lower_text = (text or "").lower()
    return (
        lower_text.split("@")[0].strip() == "/help"
        or lower_text.startswith("!хелп")
        or lower_text.startswith("!допомога")
    )


@dp.message_handler(lambda message: starts_with_help_command(message.text))
async def help_command(message: types.Message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )
        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}"
        )

        # Посилання на статтю з допомогою
        help_article_url = "https://telegra.ph/Help--TailFox-bot-ru-12-21"

        # Перекладений текст з посиланням на статтю
        translated_help_text = (
            f"{translate_text(language, 'Список команд:')}\n{help_article_url}"
        )

        await message.answer(translated_help_text)
    except Exception as e:
        logging.error("Problem with command HELP", exc_info=True)


def starts_with_name_command(text):
    lower_text = (text or "").lower()
    return any(lower_text.startswith(prefix) for prefix in ("/set_name", "!лисичка"))


@dp.message_handler(lambda message: starts_with_name_command(message.text))
async def set_name_command_new(message: types.Message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )

        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}"
        )

        # Розбиваємо повідомлення на дві частини: команду і аргументи після команди
        parts = message.text.split(maxsplit=1)
        command = parts[0].lower()

        # Якщо є аргументи після команди
        if len(parts) > 1:
            new_nickname = parts[1].strip()

            if not new_nickname or "@" in new_nickname:
                await message.reply(
                    translate_text(
                        language, "В нікнеймі не можна використовувати символ '@'."
                    )
                )
            elif len(new_nickname) > 15:
                await message.reply(
                    translate_text(
                        language, "Нікнейм повинен бути не більше 15 символів."
                    )
                )
            else:
                # Збереження нового нікнейму в базі даних
                update_user_nickname(user_id, new_nickname)
                await message.reply(
                    f"{message.from_user.first_name}, {translate_text(language, 'твій нікнейм був успішно змінений на:')} {new_nickname}."
                )

        else:
            # Якщо аргументів після команди немає
            if command == "!лисичка":
                await message.reply(
                    f"{translate_text(language, 'Для зміни нікнейму введіть новий нікнейм після')} !лисичка"
                )
            elif command == "/set_name":
                await message.reply(
                    f"{translate_text(language, 'Для зміни нікнейму введіть новий нікнейм після')} /set_name"
                )
    except Exception as e:
        logging.error("Problom command /set_name", exc_info=True)


class YourStateName(StatesGroup):
    new_name = State()


@dp.message_handler(state=YourStateName.new_name)
async def process_new_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    new_nickname = (message.text or "").strip()
    if not new_nickname or len(new_nickname) > 15 or "@" in new_nickname:
        await message.reply("Имя должно содержать 1–15 символов без @.")
        return
    chat_id = message.chat.id
    language = get_chat_language(chat_id)

    # Збереження нового нікнейму в базі даних
    update_user_nickname(user_id, new_nickname)

    await state.finish()
    await message.reply(
        f"{message.from_user.first_name}, {translate_text(language, 'твій нікнейм був успішно змінений на:')} {new_nickname}"
    )


def starts_with_nick_command(text):
    lower_text = (text or "").lower()
    return any(lower_text.startswith(prefix) for prefix in ("/name", "!ник", "кличка"))


@dp.message_handler(lambda message: starts_with_nick_command(message.text))
async def show_name_command(message: types.Message):
    try:
        user_id = message.from_user.id
        user_nickname = get_user_nickname(user_id)
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )

        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}"
        )

        await message.reply(
            f"{translate_text(language, 'Ваш поточний нікнейм:')} {user_nickname}"
        )
    except Exception as e:
        logging.error("Problem command show_name", exc_info=True)


def information_with_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ["/group", "!інформація", "!инфо", "!інфо"]


@dp.message_handler(lambda message: information_with_command(message.text))
async def stats(message: types.Message):
    try:
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )

        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}"
        )

        # Обчислити час роботи бота без перебоїв
        current_time = datetime.now()
        uptime = current_time - START_TIME
        formatted_uptime = format_timedelta(uptime)  # Форматування timedelta

        # Отримати використану пам'ять
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # у Мб
        # у Мб

        if message.from_user.id in YOUR_USER_ID:  # Адміністратор
            users_count = cursor.execute(
                "SELECT COUNT(DISTINCT id) FROM users"
            ).fetchone()[0]
            active_users_count = cursor.execute(
                'SELECT COUNT(DISTINCT id) FROM users WHERE last_active_date > datetime("now", "-7 days")'
            ).fetchone()[0]
            groups_count = cursor.execute(
                "SELECT COUNT(DISTINCT chat_id) FROM Chats WHERE chat_id < 0"
            ).fetchone()[0]

            await message.reply(
                f"{translate_text(language, 'Кількість користувачів:')} {users_count}\n"
                f"{translate_text(language, 'Кількість активних лисичок:')} {active_users_count}\n"
                f"{translate_text(language, 'Кількість груп:')} {groups_count}\n"
                f"{translate_text(language, 'Час роботи без перебоїв:')} {formatted_uptime}\n"
                f"{translate_text(language, 'Використання памяті:')} {memory_usage:.2f}{translate_text(language, 'МБ')}"
            )

        else:  # Звичайний користувач
            # Витягнути загальну статистику
            users_count = cursor.execute(
                "SELECT COUNT(DISTINCT id) FROM Users"
            ).fetchone()[0]
            groups_count = cursor.execute(
                "SELECT COUNT(DISTINCT chat_id) FROM Chats WHERE chat_id < 0"
            ).fetchone()[0]

            await message.reply(
                f"{translate_text(language, 'Кількість користувачів:')} {users_count}\n"
                f"{translate_text(language, 'Кількість груп:')} {groups_count}\n"
                f"{translate_text(language, 'Час роботи без перебоїв:')}{formatted_uptime}\n"
                f"{translate_text(language, 'Використання памяті:')} {memory_usage:.2f}{translate_text(language, 'МБ')}"
            )
    except Exception as e:
        logging.error("Problem command /info", exc_info=True)


# Обробник для зберігання кожного повідомлення з групи


# Команда для розсилки повідомлення
@dp.message_handler(lambda message: (message.text or "").startswith("!розсилка"))
async def broadcast_to_groups(message: types.Message):
    global broadcast_message
    message_to_broadcast = (
        message.reply_to_message if message.reply_to_message else broadcast_message
    )

    if message_to_broadcast is None:
        await message.reply("Немає повідомлення для розсилки.")
        return

    if message.from_user.id == ADMIN_ID:
        group_chat_ids = cursor.execute(
            "SELECT chat_id FROM Chats WHERE chat_id < 0"
        ).fetchall()
        total_chats = len(group_chat_ids)
        successful_sends = 0
        failed_chats = []

        for chat_id in group_chat_ids:
            try:
                await bot.forward_message(
                    chat_id[0],
                    message_to_broadcast.chat.id,
                    message_to_broadcast.message_id,
                )
                successful_sends += 1
                await asyncio.sleep(1)  # Встановіть тайм-аут відповідно до ваших вимог
            except Exception as e:
                logging.error(
                    f"Помилка при відправці повідомлення в чат {chat_id[0]}: {e}"
                )
                failed_chats.append(chat_id[0])

        summary = f"Розсилка завершена! Успішно відправлено {successful_sends} з {total_chats} повідомлень."
        if failed_chats:
            summary += (
                "\nНе вдалося відправити повідомлення в наступних групах:\n"
                + ", ".join(map(str, failed_chats))
            )

        await bot.send_message(ADMIN_ID, summary)
    else:
        await message.reply("Ви не маєте доступу до цієї команди!")


def is_hug_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ["hug", "обняти", "обнять"]


@dp.message_handler(lambda message: is_hug_command(message.text))
async def process_hug_command(message: types.Message):
    try:
        sender_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)

        if sender_id == ADMIN_ID:
            sender_display_name = MY_CUSTOM_NAME  # ваше специфічне ім'я
        else:
            sender_username = message.from_user.full_name
            sender_display_name = (
                f"{sender_username}" if sender_username else message.from_user.full_name
            )

        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )
        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.username} в чаті '{chat_title}' використав команду: {message.text}"
        )

        if not is_user_in_db(sender_id):
            add_user_to_db(sender_id, message.from_user.username)

        if message.reply_to_message:
            receiver_id = message.reply_to_message.from_user.id
            receiver_username = message.reply_to_message.from_user.full_name
            if (
                receiver_id == ADMIN_ID
            ):  # Якщо вас "кусають", відобразити ваше специфічне ім'я
                receiver_display_name = MY_CUSTOM_NAME
            else:
                receiver_display_name = (
                    f"{receiver_username}"
                    if receiver_username
                    else message.reply_to_message.from_user.full_name
                )

            self_hug_translations = [
                translate_text(
                    language,
                    "{sender_display_name} відчув одинокість і окутав сам себе хвостиком. Інколи нам всім потрібно трохи самообіймів!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} обіймає сам себе, знаючи, що інколи найкращі обійми - це ті, які ми даємо собі.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} згортається у клубочок, окутуючи себе своїм хвостиком. Інколи самообійми - це все, що нам потрібно.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} ніжно обіймає сам себе, нагадуючи всім нам про важливість самолюбові.",
                ),
                translate_text(
                    language,
                    "Нехай інші говорять, що хочуть, {sender_display_name} знає, що обіймати себе - це теж чудово!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} піклується про свої емоції, окутуючи себе в теплі самообійми.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} насолоджується моментом самообіймів, ніби танцюючи з власним хвостиком. Іноді найкращий партнер - це сам себе.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} створює магію самообіймів, плавно переплітаючи рухи і емоції. Він(вона) заслуговує на цей танець самолюбові!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} віддається самообіймам, немов чарівно поглиблюючись у власний обійм. Інколи найкращий момент - це момент самолюбові!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} створює неповторний момент, обіймаючи сам себе. Справжній майстер обіймів власного щастя!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} обіймає себе з любов'ю, немов художник створює своє шедевральне полотно. Самообійми - це висловлювання любові до себе.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} поглиблюється в самообіймах, наче в найкращому романтичному фільмі, де вона(він) - головний герой(героїня) свого життя.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} танцює з власним хвостиком, обіймаючи себе в ритмі своєї власної мелодії щастя. Справжній танець самолюбові!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} створює арт самообіймів, ніби розфарбовуючи світ своєї внутрішньої гармонії. Художник свого щастя!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} наслідує витонченість самообіймів, неначе творчий геній у світі власної щасливої реальності.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} відчуває невичерпність самообіймів, мов глядач свого власного феєричного виставища щасливих митей.",
                ),
            ]
            actions_translations = [
                translate_text(
                    language, "{sender} окутав {receiver} хвостиком, приносячи комфорт."
                ),
                translate_text(
                    language,
                    "{sender} спробував обняти {receiver}, але {receiver} ухилився.",
                ),
                translate_text(
                    language, "{sender} обіймав {receiver} так сильно, що майже здавив!"
                ),
                translate_text(
                    language,
                    "{sender} обіймав {receiver}, але {receiver} ловко уник обіймів, використовуючи свій хвостик.",
                ),
                translate_text(
                    language,
                    "{receiver} відчув, як хвостик {sender} легко торкнувся його, створюючи атмосферу ніжності.",
                ),
                translate_text(
                    language,
                    "{sender} намагався обняти {receiver}, але їх хвостики заплуталися. Сміх і радість!",
                ),
                translate_text(
                    language,
                    "{receiver} відчув ніжне обіймання від {sender} і не міг стримати посмішку.",
                ),
                translate_text(
                    language,
                    "{sender} обіймав {receiver} так легко, що це більше схоже на гру хвостиками.",
                ),
                translate_text(
                    language,
                    "{sender} намагався обіймати {receiver}, але натомість просто лоскотав його хвостиком.",
                ),
                translate_text(
                    language,
                    "{receiver} почувався як у захваті, коли {sender} окутав його своїм пухнастим хвостиком.",
                ),
                translate_text(
                    language,
                    "{sender} обіймає {receiver} так сильно, що він(вона) втрачає рухливість.",
                ),
                translate_text(
                    language,
                    "{sender} прагне обійняти {receiver} і закручує його хвіст на рівні шиї. Ой!",
                ),
                translate_text(
                    language,
                    "{sender} різко обіймає {receiver} і відштовхує його, роблячи неочікуваний рух.",
                ),
                translate_text(
                    language,
                    "{sender} спробовав обняти {receiver}, але просто присів на нього. Не самий зручний хід!",
                ),
                translate_text(
                    language,
                    "{receiver} відчуває, як {sender} обгортає його ззаду, викликаючи сміх та невдоволення.",
                ),
                translate_text(
                    language,
                    "{sender} намагається обійняти {receiver}, але забуває про хвіст і торкається обличчям. Ой-ой!",
                ),
                translate_text(
                    language,
                    "{receiver} відчуває, як {sender} різко стискає його, демонструючи велику енергію.",
                ),
                translate_text(
                    language,
                    "{sender} обгортає {receiver} хвостиком, але занадто сильно стискає, викликаючи дискомфорт.",
                ),
                translate_text(
                    language,
                    "{sender} обіймає {receiver}, але випадково застукує його хвіст об ліжко. Ай-ай-ай!",
                ),
                translate_text(
                    language,
                    "{sender} різко звертається, обіймаючи {receiver}, але залишається занадто близько до обличчя. Непорозуміння!",
                ),
            ]
            # Щоб використовувати ці переклади у відповідях:
            if sender_id == receiver_id:
                translated_text = random.choice(self_hug_translations)
                await message.answer(
                    translated_text.format(sender_display_name=sender_display_name)
                )
            else:
                selected_action = random.choice(actions_translations)
                response = selected_action.format(
                    sender=sender_display_name, receiver=receiver_display_name
                )
                await message.answer(response)
                update_last_active_date(sender_id)
        else:
            await message.answer(
                translate_text(
                    language,
                    "Відповідь на повідомлення користувача, якого потрібно обійняти.",
                )
            )
    except Exception as e:
        logging.error("Problem command /hug", exc_info=True)


def is_bit_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    result = lower_text[0] in ["кусь", "вкусити", "вкусить"]
    return result


@dp.message_handler(lambda message: is_bit_command(message.text))
async def process_bite_command(message: types.Message):
    try:
        sender_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)

        if sender_id == ADMIN_ID:
            sender_display_name = MY_CUSTOM_NAME  # ваше специфічне ім'я
        else:
            sender_username = message.from_user.full_name
            sender_display_name = (
                f"{sender_username}" if sender_username else message.from_user.full_name
            )

        chat_title = (
            message.chat.title or message.chat.username or message.chat.first_name
        )
        logging.info(
            f"Користувач {message.from_user.full_name} {message.from_user.username} в чаті '{chat_title}' використав команду: {message.text}"
        )

        if not is_user_in_db(sender_id):
            add_user_to_db(sender_id, message.from_user.username)

        if message.reply_to_message:
            receiver_id = message.reply_to_message.from_user.id
            receiver_is_bot = message.reply_to_message.from_user.is_bot
            receiver_username = message.reply_to_message.from_user.full_name
            if (
                receiver_id == ADMIN_ID
            ):  # Якщо вас "кусають", відобразити ваше специфічне ім'я
                receiver_display_name = MY_CUSTOM_NAME
            else:
                receiver_display_name = (
                    f"{receiver_username}"
                    if receiver_username
                    else message.reply_to_message.from_user.full_name
                )

            if receiver_is_bot:
                await message.answer(
                    translate_text(language, "Не кусай роботів, зуби зломиш!")
                )
                return

            self_bite_translations = [
                translate_text(
                    language,
                    "{sender_display_name} відчув дивний імпульс і куснув себе. Але що це значить?",
                ),
                translate_text(
                    language,
                    "{sender_display_name} вирішив покусати себе. Це було дивно, але якось весело.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} ковзнув хвостиком і несподівано відчув, як зуби торкаються його хвостика. Чарівність моменту!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} грався зі своїм хвостиком і раптом відчув легке кусання. О, які вони гострі!",
                ),
                translate_text(
                    language,
                    "{sender_display_name} відчув неймовірний зуд і куснув себе. Хмм, це відчуття...",
                ),
                translate_text(
                    language,
                    "Нахиливши голову, {sender_display_name} легенько куснув себе за хвостик. 'Опа, несподівано!' - подумав він.",
                ),
                translate_text(
                    language,
                    "Граючись зі своїм пухнастим хвостиком, {sender_display_name} несподівано куснув його. Хочеться сміятися й плакати одночасно.",
                ),
                translate_text(
                    language,
                    "Цікавість взяла гору, і {sender_display_name} куснув себе. 'Оу, це я...' - подумав він, відчуваючи смак своєї шерсті.",
                ),
                translate_text(
                    language,
                    "Спробуючи дізнатися, як смакує хвостик, {sender_display_name} легенько куснув себе. Враження змішані.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} навіть не замислювався, просто куснув себе. Якось дивно, але й цікаво в той же час.",
                ),
                translate_text(
                    language,
                    "{sender_display_name} провів зубами по своєму хвостику, ковзаючи між пухнастими пасмами. Це було дивно... але приємно.",
                ),
            ]

            actions_translations = [
                translate_text(
                    language,
                    "{sender} куснув {receiver}, і атмосфера стала дещо напруженою.",
                ),
                translate_text(
                    language,
                    "{sender} спробував куснути {receiver}, але {receiver} відступив назад вчасно.",
                ),
                translate_text(
                    language,
                    "{sender} куснув {receiver} так сильно, що майже залишив слід!",
                ),
                translate_text(
                    language,
                    "{sender} ковзнув хвостиком і куснув {receiver}, викликаючи здивування.",
                ),
                translate_text(
                    language,
                    "{receiver} спостерігав, як {sender} малює круги хвостиком, поки не відчув різке кусання.",
                ),
                translate_text(
                    language,
                    "{sender} крадькома підкрався і куснув {receiver}, і тепер їх хвостики заплуталися.",
                ),
                translate_text(
                    language,
                    "Хвостик {sender} злетів угору і куснув {receiver} – це був знак дружби... або виклику.",
                ),
                translate_text(
                    language,
                    "{sender} зробив вигук і куснув {receiver} так швидко, що це могло бути пропущено.",
                ),
                translate_text(
                    language,
                    "{receiver} відчув легке кусання і побачив, що {sender} сміється з його реакції.",
                ),
                translate_text(
                    language,
                    "{sender} спробував куснути {receiver}, але міг куснути лише повітря.",
                ),
                translate_text(
                    language,
                    "{sender} куснув {receiver} і пішов, пишаючись своїм “хитрим” ходом.",
                ),
                translate_text(
                    language,
                    "Хвостик {sender} закрутився, як спіраль, коли він куснув {receiver}, який не міг стримати сміх.",
                ),
            ]

            update_last_active_date(sender_id)

            if sender_id == receiver_id:
                translated_text = random.choice(self_bite_translations)
                await message.answer(
                    translated_text.format(sender_display_name=sender_display_name)
                )
            else:
                selected_action = random.choice(actions_translations)
                response = selected_action.format(
                    sender=sender_display_name, receiver=receiver_display_name
                )
                await message.answer(response)
                update_last_active_date(sender_id)
        else:
            await message.answer(
                translate_text(
                    language,
                    "Відповідь на повідомлення користувача, якого потрібно куснути.",
                )
            )
    except Exception as e:
        print(e)
        logging.error("Problem command /bite", exc_info=True)


def is_reset_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ["reset", "ресет"]


@dp.message_handler(lambda message: is_reset_command(message.text))
async def reset_command(message: types.Message):
    user_id = message.from_user.id

    # Перевірте, чи є користувач адміністратором
    if not is_admins(user_id):
        await message.reply("Тільки мій татко може використовувати цю команду!")
        return

    # Визначте ID користувача, якому потрібно скинути таймер
    target_user_id = (
        message.reply_to_message.from_user.id if message.reply_to_message else None
    )
    if target_user_id:
        reset_user_timer(target_user_id)
        await message.reply(
            f"Користувач {message.reply_to_message.from_user.full_name} може ще раз виростити хвостик."
        )
    else:
        await message.reply(
            "Відповідь на повідомлення користувача, якому потрібно скинути таймер."
        )


def is_bite_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ["bite", "откусить", "відкусити"]


@dp.message_handler(lambda message: is_bite_command(message.text))
async def bite_tail(message: types.Message):
    try:
        biting_user = message.from_user.id
        bitten_user = (
            message.reply_to_message.from_user.id if message.reply_to_message else None
        )
        biting_nickname = get_nickname_from_db(biting_user)
        bitten_nickname = get_nickname_from_db(bitten_user) if bitten_user else None
        biting_username = (
            biting_nickname
            if biting_nickname
            else (
                message.from_user.username
                if message.from_user.username
                else message.from_user.first_name
            )
        )
        bitten_username = (
            bitten_nickname
            if bitten_nickname
            else (
                message.reply_to_message.from_user.username
                if message.reply_to_message
                and message.reply_to_message.from_user.username
                else (
                    message.reply_to_message.from_user.first_name
                    if message.reply_to_message
                    else None
                )
            )
        )
        update_last_active_date(biting_user)
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        bite_responses = [
            translate_text(
                language,
                "{biting_username} хитро відкусив {tail_loss} см хвостика у {bitten_username} 😏, при цьому втративши {teeth_loss} {teeth_ending} 😬.",
            ),
            translate_text(
                language,
                "Лисичка {biting_username} підступно захопила {tail_loss} см хвостика у {bitten_username} 🦊 та пошкодила {teeth_loss} {teeth_ending} 🙊.",
            ),
            translate_text(
                language,
                "Зі сміхом, лисичка {biting_username} відкусила {tail_loss} см хвостика у {bitten_username} 😂, не звертаючи уваги на втрату {teeth_loss} {teeth_ending} 😅.",
            ),
            translate_text(
                language,
                "Зі словами 'Тобі це не потрібно, правда?' 😜, {biting_username} відкусив {tail_loss} см хвостика у {bitten_username}, але платіж був високий - втрачено {teeth_loss} {teeth_ending} 😖.",
            ),
            translate_text(
                language,
                "Поки {bitten_username} милувався краєвидами 🌄, лисичка {biting_username} хитро захопила {tail_loss} см його хвостика. Ціна жарту - {teeth_loss} {teeth_ending} 😆.",
            ),
            translate_text(
                language,
                "{biting_username}, з грою в очах 😈, спробував на смак хвостик {bitten_username} і отримав у винагороду {tail_loss} см. Але хитрощі коштують: втратив {teeth_loss} {teeth_ending} 😓.",
            ),
            translate_text(
                language,
                "Не чекаючи запрошення на танець 💃, {biting_username} рішуче відкусив {tail_loss} см хвостика у {bitten_username}. Та хитра лисичка втратила {teeth_loss} {teeth_ending} у цій авантюрі 🤕.",
            ),
            translate_text(
                language,
                "Зі словами 'Заберу собі на пам'ять!' 🥰, {biting_username} захопив {tail_loss} см хвостика у {bitten_username}. Однак кожна пам'ятка має свою ціну - втрачено {teeth_loss} {teeth_ending} 😟.",
            ),
        ]

        fail_responses = [
            translate_text(
                language, "Ти не зміг вкусити користувача і втратив один зуб 😢."
            ),
            translate_text(
                language,
                "Ой! Твоя спроба вкусити не була успішною 😓. Мінус один зуб 🙁.",
            ),
            translate_text(
                language,
                "Користувач виявився слизьким! Ти не зміг його вкусити і втратив зуб 😩.",
            ),
            translate_text(
                language, "Твоя спроба вкусити зазнала невдачі 😔. Зламаний зуб 🦷!"
            ),
            translate_text(
                language,
                "Ой, лисичко 🦊! Твої хитрощі сьогодні не спрацювали 😕. Втратив зуб, але не втратив амбіцій 💪!",
            ),
            translate_text(
                language,
                "Лисичка {biting_username}, можливо, хвостик {bitten_username} був завеликий для твоїх зубків? 🤔 Один зуб менше, але нехай це буде уроком 📖!",
            ),
            translate_text(
                language,
                "Зі словами 'Так легко мене не проведеш!' 😎, {bitten_username} уник твоєї спроби. І ось тобі пам'ятка - втрачений зуб 😞.",
            ),
            translate_text(
                language,
                "Можливо, {bitten_username} просто має хороший день 🌞, а ти, на жаль, ні 😖. Мінус один зуб, лисичко 🦊.",
            ),
            translate_text(
                language,
                "Ах, лисичка! Іноді найкраща стратегія - це просто сісти і дочекатись кращого моменту 🤷. А поки що - втратив зуб 😭.",
            ),
        ]

        if not bitten_user:
            await bot.send_message(
                chat_id,
                text=f"{translate_text(language, 'Відповідь на повідомлення користувача, якого хочете вкусити.')}",
            )
            return
        try:
            chat_member = await bot.get_chat_member(chat_id, bitten_user)
        except Exception as e:
            logging.error(f"Не вдалося отримати дані члена чату: {e}")
            await message.reply(
                translate_text(
                    language,
                    "Вибачте, сталася непередбачувана помилка. Спробуйте ще раз пізніше.",
                )
            )
            return

        if chat_member and chat_member.status not in [
            "member",
            "administrator",
            "creator",
        ]:
            # Якщо користувач не є членом чату або був видалений, відправте повідомлення
            await bot.send_message(
                chat_id,
                text=translate_text(
                    language,
                    "{} втік в ліс та сховався у своїй норці. Не можна його вкусити! 🦊🌲",
                ).format(bitten_username),
            )
            return

        if biting_user == bitten_user:
            await message.reply(
                f"{translate_text(language, 'Ви не можете вкусити себе.')}"
            )
            return

        if message.reply_to_message.from_user.is_bot:
            await message.reply(
                f"{translate_text(language, 'Ви не можете вкусити бота.')}"
            )
            return

        result = apply_bite(
            biting_user,
            bitten_user,
            random.random() < 0.3,
            teeth_loss=random.randint(1, 5),
            tail_loss=random.randint(1, 8),
        )
        errors = {
            "missing_user": "Этот игрок ещё не зарегистрирован. Пусть сначала напишет боту.",
            "short_tail": f"{bitten_username} имеет хвостик меньше 100 см.",
            "no_teeth": "У тебя нет зубов для укуса.",
            "daily_limit": f"{bitten_username} уже потерял 20 см хвоста сегодня.",
        }
        if result.get("error"):
            await message.reply(errors[result["error"]])
            return
        if result["success"]:
            await message.reply(
                random.choice(bite_responses).format(
                    biting_username=biting_username,
                    bitten_username=bitten_username,
                    tail_loss=result["tail_loss"],
                    teeth_loss=result["teeth_loss"],
                    teeth_ending=get_teeth_ending(result["teeth_loss"], language),
                )
            )
        else:
            await message.reply(
                random.choice(fail_responses).format(
                    biting_username=biting_username, bitten_username=bitten_username
                )
            )

    except Exception as e:
        logging.error(
            f"Помилка при обробці команди від користувача {message.from_user.username if message.from_user.username else message.from_user.first_name}: {e}"
        )
        await message.reply(
            translate_text(
                language,
                "Вибачте, сталася непередбачувана помилка. Спробуйте ще раз пізніше.",
            )
        )


@dp.message_handler(lambda message: (message.text or "").startswith("!!дать"))
async def give_or_take_teeth(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        try:
            # Виділити кількість зубів з повідомлення
            teeth_operation = (
                message.text.split()[1] if len(message.text.split()) > 1 else None
            )
            if teeth_operation and teeth_operation.startswith("+"):
                teeth_amount = int(
                    teeth_operation[1:]
                )  # Пропускаємо знак і конвертуємо решту строки в число
                operation = "додано"
            elif teeth_operation and teeth_operation.startswith("-"):
                teeth_amount = -int(teeth_operation[1:])  # І тут також
                operation = "забрано"
            else:
                await message.reply(
                    "Будь ласка, вкажіть '+' або '-' перед кількістю зубів!"
                )
                return

            # Виділити ID користувача
            user_id = (
                message.reply_to_message.from_user.id
                if message.reply_to_message
                else None
            )
            if user_id:
                add_or_remove_teeth(
                    user_id, teeth_amount
                )  # Функція вже може обробляти від'ємні числа, тому немає потреби в abs
                await message.reply(
                    f"Користувачу {message.reply_to_message.from_user.full_name} {operation} {abs(teeth_amount)} зубів!"
                )
            else:
                await message.reply(
                    "Не можу визначити користувача, якому потрібно додати або забрати зуби!"
                )
        except ValueError:
            await message.reply(
                "Будь ласка, вкажіть дійсну кількість зубів і використовуйте '+' або '-' для додавання або віднімання зубів!"
            )
    else:
        await message.reply("Лише мій татко може використовувати цю команду!")


def is_fox_command(text):
    lower_text = (
        (text or "").lower().strip()
    )  # Використання strip() для видалення початкових і кінцевих пробілів
    if not lower_text:
        return False

    # Перевірка, чи рядок починається з одного з виразів
    if lower_text.startswith(("ня фр", "ня фир", "ня фыр")):
        return "anime"
    elif lower_text.startswith(("fox", "фыр", "фр", "фир")):
        return "normal"
    return False


@dp.message_handler(lambda message: is_fox_command(message.text) != False)
async def send_fox_media(message: types.Message):
    command_type = is_fox_command(message.text)

    if command_type == "anime":
        # Використання ключа 'kitsune' для отримання URL зображення аніме лисички
        url_kitsune = sources["sfw"]["kitsune"]
        url_fox_girl = sources["sfw"]["fox_girl"]
        # Ви можете вибрати один із цих URL або випадковим чином вибрати між ними
        url = random.choice([url_kitsune, url_fox_girl])
        image_url = await get_image(url)
        await message.reply_photo(
            image_url, caption=""
        ) if image_url else await message.reply("Не вдалося отримати зображення.")
    elif command_type == "normal":
        # Використання ключа 'fox_girl' для отримання URL звичайної лисички
        url = sources["sfw"]["fox"]
        image_url = await get_fox_image()
        await message.reply_photo(
            image_url, caption=""
        ) if image_url else await message.reply("Не вдалося отримати зображення.")


def predict_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    return lower_text[0] in [
        "/predict",
        "!расскажи",
        "!предсказание",
        "/predict@tailfox_bot",
    ]


# Завантаження передбачень з файлу
def read_predictions(language):
    file_path = BASE_DIR / "predictions.json"
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            predictions_data = json.load(file)
            # Доступ до передбачень відповідно до вказаної мови
            return predictions_data.get(language, predictions_data.get("ru", []))
    except Exception as e:
        logging.error(f"Помилка при читанні файла передбачень: {e}")
        return []


def can_use_command(last_used_time):
    previous = parse_datetime(last_used_time)
    if not previous:
        return True
    tz = pytz.timezone("Europe/Kyiv")
    return pytz.utc.localize(previous).astimezone(tz).date() < datetime.now(tz).date()


def get_time_until_reset():
    tz = pytz.timezone("Europe/Kyiv")
    now = datetime.now(tz)
    tomorrow = now.date() + timedelta(days=1)
    midnight = tz.localize(datetime.combine(tomorrow, datetime.min.time()))
    return midnight - now


@dp.message_handler(lambda message: predict_command(message.text))
async def cmd_future(message: types.Message):
    user_id = message.from_user.id
    language = get_chat_language(message.chat.id)
    record_activity(user_id, message.from_user.full_name, message.chat.id)
    choices = read_predictions(language)
    if not choices:
        await message.reply("Не удалось загрузить предсказания.")
        return
    if claim_prediction(user_id):
        await message.answer(
            f"{message.from_user.full_name}, "
            + translate_text(language, "твоє передбачення: \n\n")
            + str(random.choice(choices))
            + "\n\nЗавтра будет новое."
        )
    else:
        seconds = int(get_time_until_reset().total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        await message.answer(
            f"{message.from_user.full_name}, "
            + translate_text(language, "наступне передбачення через: \n")
            + format_time(hours, minutes, language)
        )


def idea_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ["/idea", "!ідея", "!идея"]


@dp.message_handler(lambda message: idea_command(message.text))
async def forward_idea_to_admin(message: types.Message):
    try:
        # Пересилання повідомлення адміністратору
        await bot.forward_message(FARMANDER_ID, message.chat.id, message.message_id)

        # Видалення повідомлення в чаті після пересилання
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        await message.reply("Не удалось передать идею администратору.")


def image_command(text):
    lower_text = (text or "").lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ["/image", "!создай"]


MAX_TELEGRAM_FILE_SIZE = 5000000  # Максимальный размер файла для Telegram (в байтах)


@dp.message_handler(lambda message: image_command(message.text))
async def generate_image(message: types.Message):
    words = (message.text or "").split(maxsplit=1)
    if len(words) < 2:
        await message.reply("Формат: /image описание картинки")
        return
    progress = await message.reply("Создаю картинку...")
    data = {
        "prompt": words[1],
        "model": "pixart-a",
        "data": {"width": 1024, "height": 1024, "image_style": "Anime"},
    }
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120)
        ) as session:
            async with session.post(
                "https://nexra.aryahcr.cc/api/image/complements", json=data
            ) as response:
                response.raise_for_status()
                if response.content_type.startswith("image/"):
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > MAX_TELEGRAM_FILE_SIZE:
                            raise ValueError("Image exceeds upload size limit")
                    await message.reply_photo(
                        types.InputFile(BytesIO(body), filename="image.png")
                    )
                else:
                    result = await response.json()
                    images = result.get("images") or result.get("image") or []
                    if isinstance(images, str):
                        images = [images]
                    if (
                        not images
                        or not isinstance(images[0], str)
                        or not images[0].startswith("https://")
                    ):
                        raise ValueError("API did not return an image URL")
                    await message.reply_photo(images[0])
        await progress.delete()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError):
        logging.warning("Image generation request failed")
        await progress.edit_text(
            "Сервис изображений сейчас недоступен. Попробуйте позже."
        )


ad_keywords = re.compile(
    r"\b(акция|скидка|Участвовать|промокод|распродажа|бесплатно|конкурс)\b",
    re.IGNORECASE,
)


@dp.message_handler(
    lambda m: m.from_user
    and m.from_user.is_bot
    and str(m.from_user.id) in BLOCKED_BOT_IDS,
    content_types=types.ContentTypes.ANY,
)
async def filter_messages(message: types.Message):
    try:
        # Перевірка, чи повідомлення відправлено ботом
        if message.from_user.is_bot:
            # Перевірка, чи ID бота знаходиться у списку заблокованих
            if str(message.from_user.id) in BLOCKED_BOT_IDS:
                content_type = "невідомим вмістом"

                # Перевірка на посилання або зображення
                if message.photo:
                    content_type = "зображенням"
                elif any(
                    entity.type in ["url", "text_link"]
                    for entity in (message.entities or message.caption_entities or [])
                ):
                    content_type = "посиланням"
                # Додаткова перевірка на рекламні ключові слова у тексті повідомлення
                elif message.text and ad_keywords.search(message.text):
                    content_type = "рекламним текстом"

                # Якщо вміст повідомлення відповідає критеріям для видалення
                if content_type != "невідомим вмістом":
                    try:
                        await message.delete()
                        logging.info(
                            f"Видалено повідомлення від бота {message.from_user.id} з {content_type}."
                        )
                    except Exception as e:
                        logging.error(f"Не вдалося видалити повідомлення: {e}")
                else:
                    logging.info(
                        f"Повідомлення від бота {message.from_user.id} пропущено, оскільки не містить забороненого вмісту."
                    )
    except Exception as e:
        logging.error(f"Eror filter {e}")


@dp.message_handler(chat_id=MAIN_CHAT_ID)
async def handle_main_chat_message(message: types.Message):
    global broadcast_message
    broadcast_message = message
