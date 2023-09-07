import aiogram
from aiogram.types import  InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, executor, types
import random
from datetime import datetime, timedelta
import psutil
import json
import asyncio
import sqlite3
import os
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import filters
import logging


bot = Bot('6011606332:AAE0qnnQOvfuUq9vj2iYb0fsAqcqn27IIzc')
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

#6011606332:AAE0qnnQOvfuUq9vj2iYb0fsAqcqn27IIzc \main bot
#6596332456:AAHpRFG9KzNQR31km0jpDvE0ReCteZUrBRw \test bot


last_used_time = {}
total_tail_growth = {}
LOG_FILENAME = 'Logging.log'
YOUR_USER_ID = (563342022, 6385190888)
#YOUR_USER_ID = 6385190888 # замініть на свій user_id
# Налаштування форматтера

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Налаштування обробника файлу
file_handler = logging.FileHandler(LOG_FILENAME,encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
# Налаштування обробника консолі
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Додаємо обидва обробники до кореневого логера
logging.getLogger().addHandler(file_handler)
logging.getLogger().addHandler(console_handler)
logging.getLogger().setLevel(logging.INFO)
logging.basicConfig(filename='Logging.log', level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

conn = sqlite3.connect('DataBase.sql')
cursor = conn.cursor()

# Функція для створення таблиці, якщо її ще не існує
def create_table():
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                total_tail_growth INTEGER DEFAULT 0,
                last_growth_time REAL DEFAULT 0,
                nickname TEXT,
                Chat_id INTEGER DEFAULT 0,
                language TEXT DEFAULT ''
            )''')
    
conn.commit()

async def clear_old_logs():
    while True:
        await asyncio.sleep(604800)  # очікуємо 1 тиждень (7 days * 24 hours * 60 minutes * 60 seconds)
        
        # Визначимо дату, до якої логи будуть зберігатися
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=7)

        # Зберігаємо актуальні логи
        updated_logs = []
        with open('Logging.log', 'r') as log_file:
            for line in log_file:
                # Це припущення, що у вашому файлі логів дата має формат "%Y-%m-%d". Виправте, якщо це не так.
                log_date_str = line.split()[0]
                try:
                    log_date = datetime.datetime.strptime(log_date_str, "%Y-%m-%d")
                    if log_date > cutoff_date:
                        updated_logs.append(line)
                except Exception as e:
                    logging.error(f"Помилка при читанні дати логу: {e}")

        # Записуємо оновлені логи назад у файл
        with open('Logging.log', 'w') as log_file:
            log_file.writelines(updated_logs)
        
        logging.info("Старі логи було автоматично очищено.")
        
        try:
            await bot.send_message(YOUR_USER_ID, "Старі логи було автоматично очищено.")
        except Exception as e:
            logging.error(f"Помилка при відправці повідомлення: {e}")

@dp.message_handler(commands=['special_command'])
async def handle_special_command(message: types.Message):
    user_id = message.from_user.id

    # Перевірка, чи є ID користувача у списку дозволених ID
    if user_id in YOUR_USER_ID:
        await message.reply("Ви маєте доступ до цієї команди!")
        # Тут ваш код для обробки команди
    else:
        await message.reply("Вибачте, ви не маєте доступу до цієї команди.")
    
def save_user_chat_ids(user_id, chat_ids):
    cursor.execute('UPDATE users SET chat_ids = ? WHERE id = ?', (chat_ids, user_id))
    conn.commit()

def add_chat_id_to_user(user_id, chat_id):
    chat_ids = get_user_chat_ids(user_id)
    if str(chat_id) not in chat_ids:
        chat_ids.append(str(chat_id))
        save_user_chat_ids(user_id, ','.join(chat_ids))
def get_user_chat_ids(user_id):
    cursor.execute('SELECT chat_id FROM chat_ids WHERE user_id = ?', (user_id,))
    result = cursor.fetchall()
    return [row[0] for row in result] if result else []

# Функція для отримання росту хвоста користувача з бази даних
def get_tail_growth(user_id):
    cursor.execute('SELECT total_tail_growth FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

# Функція для оновлення росту хвоста користувача в базі даних
def update_tail_growth(user_id, new_growth):
    cursor.execute('UPDATE users SET total_tail_growth = ? WHERE id = ?', (new_growth, user_id))
    conn.commit()    
def insert_user_data(user_id, chat_id, nickname, tail_growth):
    cursor.execute("INSERT INTO users (id, Chat_id, name, total_tail_growth) VALUES (?, ?, ?, ?)",
                   (user_id, chat_id, nickname, tail_growth))
    conn.commit()

async def is_admin(chat_id, user_id):
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ["administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False
@dp.message_handler(~filters.CommandStart(), chat_type=types.ChatType.PRIVATE)
async def ignore_other_commands(message: types.Message):
    chat_id = message.chat.id
    language = get_chat_language(chat_id)
    chat_languages[chat_id] = language
    chat_title = message.chat.title or message.chat.username or message.chat.first_name
    try:
      logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
    except Exception as e:
       print(f"Error logging the action: {e}")

    if message.chat.type == 'private':
        hand_down_smiley = "\U0001F447"
        finger_smiley = "\U0001F449"
        left_arrow_smiley = "\U0001F448"
        # Відправляємо повідомлення в приватному чаті
        text = (f'Привет, {message.from_user.first_name}! Лисёнок— бот-для выращивання хвостика только для групп (чатов)\n\n'
                'Раз в час игрок может ввести команду /tail, чтобы выростить хвостик\n'
                'Мои команды — /help\n\n'
                f'Канал лисёнка: @FoxyTail_official\n'
                f'Если у вас остались вопросы или вы хотите предложить идею, пишите нам. @Foxy_chati \n\n'
                f'Нажми на кнопку ниже чтобы добавить лисёнка в чат: {hand_down_smiley}')
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(f'{finger_smiley} Добавить бота в группу (чат) {left_arrow_smiley}', url="https://t.me/Tailtest_bot?startgroup=true")
        )
        await message.answer(text, reply_markup=markup)
REPLY_TO_JOIN_LEAVE = True


@dp.message_handler(lambda message: message.text in ["/toggle", "!приветствие", "!привітання"])
async def toggle_join_leave_reply(message: types.Message):
    try:    
        global REPLY_TO_JOIN_LEAVE
        chat_id = message.chat.id
        language = get_chat_language(chat_id)


        if not await is_admin(message.chat.id, message.from_user.id):
            await message.reply(f'{translate_text(language,"Ви не є адміністратором цього чату.")}')
            return

        REPLY_TO_JOIN_LEAVE = not REPLY_TO_JOIN_LEAVE
        status = translate_text(language, "enabled") if REPLY_TO_JOIN_LEAVE else translate_text(language, "disabled")

        response_template = translate_text(language, "Відповідь на приєднання/вихід користувачів тепер {status}.")
        await message.reply(response_template.format(status=status))

    except Exception as e:
        logging.error("problem command Pryvit", exc_info=True)    

@dp.message_handler(content_types=types.ContentType.NEW_CHAT_MEMBERS)
async def on_user_joined(message: types.Message):
    if not REPLY_TO_JOIN_LEAVE:
        return

    chat_id = message.chat.id
    language = get_chat_language(chat_id)

    chat_title = message.chat.title or message.chat.username or message.chat.first_name 

    # Логування кожного нового користувача
    for user in message.new_chat_members:
        try:
            logging.info(f"Користувач {user.full_name} {user.id} приєднався до чату '{chat_title}'.")
        except Exception as e:
            print(f"Error logging the action: {e}")

    # Створення посилань на нових користувачів
    new_users = ", ".join([f"<a href='tg://user?id={user.id}'>{user.username if user.username else user.full_name}</a>" for user in message.new_chat_members])

    await message.reply(f'{translate_text(language, "Ласкаво просимо,")} {new_users}!\n{translate_text(language, "Надіємося, вам сподобається тут.")}', parse_mode='HTML')


@dp.message_handler(content_types=types.ContentType.LEFT_CHAT_MEMBER)
async def on_user_left(message: types.Message):
    if not REPLY_TO_JOIN_LEAVE:
        return
    chat_id = message.chat.id
    language = get_chat_language(chat_id)

    chat_title = message.chat.title or message.chat.username or message.chat.first_name

    # Логування користувача, який покинув чат
    try:
        logging.info(f"Користувач {message.left_chat_member.full_name} {message.left_chat_member.id} покинув чат '{chat_title}'.")
    except Exception as e:
        print(f"Error logging the action: {e}")

    # Отримання імені користувача, який покинув чат, і його ID
    left_user_name = message.left_chat_member.username if message.left_chat_member.username else message.left_chat_member.full_name
    left_user_id = message.left_chat_member.id

    # Створення лінку на користувача
    left_user_link = f"<a href='tg://user?id={left_user_id}'>{left_user_name}</a>"

    # Відправлення повідомлення
    await message.reply(f'{translate_text(language, "покинув нас.")} {left_user_link} {translate_text(language, "пака")}\n{translate_text(language, "Сподіваємося, вам тут було комфортно.")}', parse_mode='HTML')


def update_tail_growth(user_id, additional_growth):
    try:
        current_growth = get_tail_growth(user_id)
        new_growth = current_growth + additional_growth
        cursor.execute('UPDATE users SET total_tail_growth = ? WHERE id = ?', (new_growth, user_id))
        conn.commit()
    except Exception as e:
        logging.error("Помилка функції Update_tail_growth",exc_info=True)  
def update_user_nickname(message, user_id, new_nickname):
    try:
        chat_id = message.chat.id
        cursor.execute('UPDATE users SET nickname = ?, Chat_id = ? WHERE id = ?', (new_nickname, chat_id, user_id))
        conn.commit()
        print(f"Nickname and chat_id for user_id {user_id} updated to {new_nickname}, {chat_id}")
    except Exception as e:
        logging.error("Помилка функції Update_tail_growth",exc_info=True)      

    
chat_languages = {}
reply_to_messages = {} 
languages = ["ru", "ua", "by", "en"]  # та інші мови, які ви підтримуєте
translations = {}
default_language = 'ru'
LANGUAGES_CODES = {
    "Українська": "ua",
    "Русский": "ru",
    "English": "en",
    "Белорусский": "by"
}

translations_cache = {}

def load_translation(lang_code: str) -> dict:
    try:
        with open(f"{lang_code}.json", "r", encoding="utf-8") as file:
            translations = json.load(file)
        return translations
    except FileNotFoundError:
        return {}

def translate_text(language, text: str) -> str:
    lang_code = LANGUAGES_CODES.get(language, "ru")  # Default to 'ru' if language is not recognized
    if lang_code not in translations_cache:
        translations_cache[lang_code] = load_translation(lang_code)
    return translations_cache[lang_code].get(text, text)
def load_translations(lang):
    lang_code = LANGUAGES_CODES.get(lang, "ru")
    try:
        with open(f'{lang_code}.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
def translate_text(language, text_key):
    language_translations = translations.get(language, translations.get("ru", {}))  # Default to Russian
    return language_translations.get(text_key, text_key)
LANGUAGE_NAMES = {
    "ua": "Українська",
    "en": "English",
    "ru": "Русский",
    "by": "Белорусский"
}

for lang_name in LANGUAGES_CODES:
    translations[LANGUAGES_CODES[lang_name]] = load_translations(lang_name)
@dp.message_handler(commands=['language'])
async def set_language_command(message: types.Message):
    try:   
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        logging.info(f"Current language for chat {chat_id}: {language}")
        chat_title = message.chat.title or message.chat.username or message.chat.first_name
       
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
        logging.info(f"Current language: {language}, Available languages: {LANGUAGE_NAMES}")


        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
        InlineKeyboardButton("🇺🇦 Українська 🇺🇦", callback_data="ua"),
        InlineKeyboardButton("🇬🇧 English 🇬🇧", callback_data="en"),
        InlineKeyboardButton("🇷🇺 Русский 🇷🇺", callback_data="ru"),
        InlineKeyboardButton("🇧🇾 Белорусский 🇧🇾", callback_data="by")
    )
        
        translated_lan_text = translate_text(language, "Choose your language:")
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
        await message.reply(f"{translated_lan_text} {language_name}", reply_markup=markup)
        # Збереження інформації про повідомлення користувача з командою /language
        reply_to_messages[message.chat.id] = {"message_id": message.message_id, "user_id": message.from_user.id}
    except Exception as e:
        logging.error("Помилка функції Language", exc_info=True)    
# Обробник вибору мови чату
language_flags = {
    "ua": "🇺🇦",
    "ru": "🇷🇺",
    "en": "🇺🇸",
    "by": "🇧🇾",
}
@dp.callback_query_handler(lambda query: query.data in LANGUAGES_CODES.values())
async def process_language_selection(query: types.CallbackQuery):
    try:    
        chat_id = query.message.chat.id
        language = get_chat_language(chat_id)
        chat_id = query.message.chat.id
        user_id = query.from_user.id
        language = query.data.replace("lang_", "")

        # Перевірка чи є користувач тим, хто викликав команду
        prev_message_info = reply_to_messages.get(chat_id)
        if not prev_message_info or prev_message_info["user_id"] != user_id:
            warning_text = translate_text(get_chat_language(chat_id), "This button is not for you!")
            await bot.answer_callback_query(query.id, text=warning_text)
            return

    
        chat_languages[chat_id] = language
        logging.info(f"Set language for chat {chat_id} to: {language}")
        # Якщо language вже є кодом мови, то використовуємо його напряму, інакше - шукаємо код у LANGUAGES_CODES
        lang_code = language if language in LANGUAGES_CODES.values() else LANGUAGES_CODES.get(language, "ru")

        cursor.execute('UPDATE users SET language = ? WHERE chat_id = ?', (lang_code, chat_id))
        conn.commit()
        


        translated_language_text = translate_text(language, "language_changed")
        language_name_in_current_language = translate_text(language, "language_name")

        language_flag = language_flags.get(language, "")
        response_text = f"{translated_language_text} {language_name_in_current_language} {language_flag}"
        await bot.send_message(chat_id, response_text, reply_to_message_id=prev_message_info["message_id"])
        # Чистимо після себе
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.delete()
        if chat_id in reply_to_messages:
            del reply_to_messages[chat_id]
    except Exception as e:
        logging.error("Помилка функції Language_Codes", exc_info=True)        

     
# Функція для отримання обраної мови чату
def get_chat_language(chat_id: int) -> str:
    cursor.execute('SELECT language FROM users WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return "ru"


def load_last_used_times():
    global last_used_time
    all_users_data = cursor.execute('SELECT id, last_growth_time FROM users').fetchall()
    
    unknown_type_users = []  # список для накопичення ідентифікаторів користувачів з невідомим типом
    
    for user_data in all_users_data:
        user_id, last_growth_time_value = user_data
        
        if isinstance(last_growth_time_value, str):  # якщо це рядок
            try:
                if " " in last_growth_time_value:  # Перевірка наявності дати і часу
                    last_used_time[user_id] = datetime.strptime(last_growth_time_value, '%Y-%m-%d %H:%M:%S')
                else:
                    # обробка як простий формат часу
                    today = datetime.today().date()
                    time_object = datetime.strptime(last_growth_time_value, '%H:%M:%S').time()
                    last_used_time[user_id] = datetime.combine(today, time_object)
            except ValueError:
                logging.error(f"Error parsing time for user {user_id} with value {last_growth_time_value}")
                last_used_time[user_id] = datetime.combine(datetime.today().date(), datetime.min.time())
        else:
            # Додаємо ідентифікатор користувача до списку невідомих типів
            unknown_type_users.append(str(user_id))
    
    if unknown_type_users:
        logging.error(f"Unknown type for last_growth_time for users: {', '.join(unknown_type_users)}")

def time_left(user_id):
    last_used = last_used_time.get(user_id)
    if not last_used:
        return None  # або повернути щось інше, якщо у користувача немає запису про використання
    
    # розрахунок часу, що залишився до наступного можливого використання
    next_use_time = last_used + timedelta(hours=1)
    delta = next_use_time - datetime.now()
    
    # якщо користувачу дозволено використовувати функцію, повернути 0
    if delta.total_seconds() <= 0:
        return 0
    
    # інакше повернути залишок часу в хвилинах
    return int(delta.total_seconds() // 60)

# Тест   
# Використовуйте цю функцію для скидання таймера
user_id_to_reset = 1  # Замініть на актуальний ID користувача

# Запустіть цю функцію при старті бота:
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

    logging.info(f"Language: {language}, Minutes: {minutes}, Seconds: {seconds}, Minute Text: {minute_text}, Second Text: {second_text}")

    return f'{translate_text(language, "Залишилось")} {minute_text} {second_text}'



# Існуючий код для генерації випадкового числа

def generate_random_num():
    return round(random.uniform(-4.5, 10), 1)
def starts_with_tail_command(text):
    lower_text = text.lower()
    return lower_text.startswith('/tail') or lower_text.startswith('!хвостик') or lower_text.startswith('!растить')

with open("tail_responses.json", "r", encoding="utf-8") as file:
    TAIL_RESPONSES = json.load(file)

def get_tail_response(change, language="ru"):  # Default to Russian
    for key in TAIL_RESPONSES:
        if "--" in key:
            low, high = map(float, key.split("--"))
            if low <= change <= high:
                return TAIL_RESPONSES[key].get(language, TAIL_RESPONSES[key].get("ru", f"No response found for change {change}."))
        elif "-" in key:
            low, high = map(float, key.split("-"))
            if low <= change <= high:
                return TAIL_RESPONSES[key].get(language, TAIL_RESPONSES[key].get("ru", f"No response found for change {change}."))
        else:
            if float(key) == change:
                return TAIL_RESPONSES[key].get(language, TAIL_RESPONSES[key].get("ru", f"No response found for change {change}."))
    return f"No response found for change {change} in language {language}."



@dp.message_handler(lambda message: starts_with_tail_command(message.text))
async def pump_tail_command(message: types.Message):
    try:    
        global last_used_time, total_tail_growth
        
        user_id = message.from_user.id
        chat_id = message.chat.id
        current_time = datetime.now()
        current_time_for_db = current_time.strftime('%H:%M:%S')
        chat_title = message.chat.title or message.chat.username or message.chat.first_name
        logging.info(f"User {message.from_user.full_name} {message.from_user.id} in chat '{chat_title}' used command: {message.text}")

        user_data = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if not user_data:
            cursor.execute('INSERT OR REPLACE INTO users (id, chat_id, name, last_active_date) VALUES (?, ?, ?, ?)', 
                        (user_id, chat_id, message.from_user.first_name, current_time_for_db))
        elif user_data[2] != chat_id:
            cursor.execute('UPDATE users SET chat_id = ?, last_active_date = ? WHERE id = ?', 
                        (chat_id, current_time_for_db, user_id))
        conn.commit()
        total_tail_growth[user_id] = total_tail_growth.get(user_id, 0)
        last_used_time[user_id] = last_used_time.get(user_id, datetime.now() - timedelta(days=1))  # Це задасть значення за замовчуванням на 1 день назад, якщо користувач ще не використовував команду


        if not last_used_time[user_id] or current_time - last_used_time[user_id] >= timedelta(hours=1):
            random_num = generate_random_num()
            language = get_chat_language(message.chat.id)
            if not language or language == "0":
                language = "default"
            response_template = get_tail_response(random_num, language)
            translated_text = response_template.format(abs(float(random_num)))  # використано abs() та float() тут
            await display_tail_growth(message, random_num, translated_text)
            last_used_time[user_id] = current_time
            print("Updating total_tail_growth...")
            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            cursor.execute('UPDATE users SET last_growth_time = ?, total_tail_growth = total_tail_growth + ? WHERE id = ?', (current_time_str, random_num, user_id))
            conn.commit()# Always commit changes
            print("Updated successfully!")
        else:
            language = get_chat_language(message.chat.id)
            remaining_time = timedelta(hours=1) - (current_time - last_used_time[user_id])
            await message.reply(f'{get_user_nickname_or_name(user_id)}, {translate_text(language, "You can only pump your tail once an hour!")}\n{translate_time_remaining(remaining_time, language)}')

            conn.commit()
    except Exception as e:
        logging.error("Problem command TAIL", exc_info=True)    

# Combine the nickname and name functions
def get_user_nickname_or_name(user_id):
    cursor.execute('SELECT name, nickname FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[1] or result[0]
    return translate_text(get_chat_language(user_id), "Unknown user")

# Simplified tail growth display
async def display_tail_growth(message, tail_growth, translated_text):
    user_id = message.from_user.id
    language = get_chat_language(message.chat.id)
    await message.reply(f'{get_user_nickname_or_name(user_id)}, {translated_text} {translate_text(language, "")} \n')

def get_user_nickname(user_id):
    cursor.execute('SELECT nickname FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    return translate_text(get_chat_language(user_id), result[0]) if result else translate_text(get_chat_language(user_id), "Unknown user")

def get_user_full_name(user_id):
    cursor.execute('SELECT name FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    return translate_text(get_chat_language(user_id), result[0]) if result else translate_text(get_chat_language(user_id), "Unknown user")



user_show_command = {}

def starts_with_top_command(text):
    lower_text = text.lower()
    return lower_text.startswith('/show') or lower_text.startswith('!топ') or lower_text.startswith('!топчик')

@dp.message_handler(lambda message: starts_with_top_command(message.text))
async def show_top(message: types.Message):
    try:    
        user_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)

        chat_title = message.chat.title or message.chat.username or message.chat.first_name
        
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
        
        create_table()
        cursor.execute('UPDATE users SET chat_id = ? WHERE id = ?', (chat_id, user_id))
        conn.commit()

        inline_keyboard = InlineKeyboardMarkup(row_width=1)
        inline_btn_chat = InlineKeyboardButton(
            translate_text(language, "Найдовший хвостик чату"),
            callback_data=f"top_chat:{user_id}"
        )
        inline_btn_all_chats = InlineKeyboardButton(
            translate_text(language, "Найдовший хвостик серед користувачів"),
            callback_data=f"top_all_chats:{user_id}"
        )
        inline_keyboard.add(inline_btn_chat, inline_btn_all_chats)

        response_text = translate_text(language, "В кого тут найдовший хвостик?:")
        await message.reply(response_text, reply_markup=inline_keyboard)
    except Exception as e:
        logging.error("Помилка фунції /top", exc_info=True)    


def get_top_all_chats_users():
        conn = sqlite3.connect('DataBase.sql')
        cursor = conn.cursor()

        # Запит до бази даних для отримання топ-10 користувачів з усіх чатів
        cursor.execute("SELECT id, name, total_tail_growth FROM users ORDER BY total_tail_growth DESC LIMIT 10")
        top_all_chats_users = cursor.fetchall()
        conn.close()
        return top_all_chats_users 
def user_exists(user_id):
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    return cursor.fetchone() is not None
def round_tail_growth(tail_growth):
    return round(tail_growth, 1)


def get_top_chat_users(chat_id):
    # Підключення до бази даних
    conn = sqlite3.connect('DataBase.sql')
    cursor = conn.cursor()
    # Отримання статистики користувачів для заданого чату, відсортованої за зростанням росту хвоста
    cursor.execute("SELECT id, name, nickname, total_tail_growth FROM users WHERE chat_id = ? ORDER BY total_tail_growth DESC LIMIT 10", (chat_id,))
    top_chat_users = cursor.fetchall()
    conn.close() # Закриття з'єднання з базою даних
    return top_chat_users
def round_tail_growth(tail_growth):
    return round(tail_growth, 1)
@dp.callback_query_handler(lambda query: query.data.startswith("top_"))
async def process_top_selection(query: types.CallbackQuery):
    try:    
        command, user_id = query.data.split(":")
        user_id = int(user_id)

        if user_id != query.from_user.id:
            await bot.answer_callback_query(query.id, text=translate_text(get_chat_language(query.message.chat.id), "This button is not for you!"))
            return

        chat_id = query.message.chat.id
        language = get_chat_language(chat_id)
        translated_cm_text = translate_text(language, "cm")
        
        if command == "top_chat":
            top_chat_users = get_top_chat_users(chat_id)
            if top_chat_users:
                top_users_text = "\n".join([f"{idx + 1}. {user[2] or user[1]} - {round_tail_growth(user[3])} {translated_cm_text}" for idx, user in enumerate(top_chat_users)])
                response_text = f'{translate_text(language, "Найдовший хвостик чату:")}\n{top_users_text}'
            else:
                response_text = translate_text(language, "На жаль, тут ще немає користувачів з хвостиками.")
        
        elif command == "top_all_chats":
            top_all_chats_users = get_top_all_chats_users()
            if top_all_chats_users:
                top_users_text = "\n".join([f"{idx + 1}. {get_user_display_name(user)} - {round_tail_growth(user[2])} {translated_cm_text}" for idx, user in enumerate(top_all_chats_users)])
                response_text = f'{translate_text(language, "Найдовший хвостик серед користувачів:")}\n{top_users_text}'
            else:
                response_text = translate_text(language, "На жаль, ще немає чатів з хвостиками.")

        if query.message:
                # Зберегти ідентифікатор повідомлення перед видаленням
            reply_to_message_id = query.message.reply_to_message.message_id if query.message.reply_to_message else None

            await bot.delete_message(chat_id, query.message.message_id)

            if reply_to_message_id:
                try:
                        await bot.send_message(chat_id, response_text, reply_to_message_id=reply_to_message_id)
                except aiogram.utils.exceptions.BadRequest:
                        await bot.send_message(chat_id, response_text)
            else:
                await bot.send_message(chat_id, response_text)


    except Exception as e:
        logging.error("Помилка виводу топу", exc_info=True)        

def get_user_display_name(user):
    user_nickname = get_user_nickname(user[0])  # Отримуємо нікнейм за user_id
    return user_nickname or user[1]


def round_tail_growth(tail_growth):
    return round(tail_growth, 1)     

#ПРОФІЛЬ
def starts_with_prof_command(text):
    lower_text = text.lower()
    return lower_text.startswith('/prof') or lower_text.startswith('!профіль') or lower_text.startswith('!профиль')

@dp.message_handler(lambda message: starts_with_prof_command(message.text))
async def prof(message: types.Message):
    try:    
        user_id = message.from_user.id
        user_first_name = message.from_user.first_name
        user_nickname = get_user_nickname(user_id)
        user_tail_growth = get_tail_growth(user_id)
        rounded_tail_growth = round_tail_growth(user_tail_growth)
        chat_title = message.chat.title or message.chat.username or message.chat.first_name
     
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
       
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        translated_cm_text = translate_text(language, "cm")

        if user_tail_growth > -50:
            name_or_nickname = user_nickname or user_first_name
            await message.reply(f'{translate_text(language, "Тебе називають:")} {name_or_nickname}\n{translate_text(language, "Довжина твого хвостика:")} {rounded_tail_growth} {translated_cm_text}.')
        else:
            name_or_nickname = user_nickname or user_first_name
            await message.reply( f'{translate_text(language, "Тебе називають:")} {name_or_nickname}\n{translate_text(language, "На жаль в тебе ше немає хвостика.")}')
    except Exception as e:
        logging.error("Problem open profile", exc_info=True)        




def starts_with_help_command(text):
    lower_text = text.lower()
    return lower_text.startswith('/help') or lower_text.startswith('!хелп') or lower_text.startswith('!допомога')


@dp.message_handler(lambda message: starts_with_help_command(message.text))
async def help_command(message: types.Message):
    try:    
        user_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = message.chat.title or message.chat.username or message.chat.first_name
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
        
        translated_help_text = translate_text(language, "Список команд:")
        commands_list = [
            ("/tail|!хвостик|!растить", "Виростити хвіст"),
            ("/help|!хелп!|!допомога", "Вивести перелік команд"),
            ("/show|!топчик|!топ", "Показати топ користувачів чату"),
            ("/prof|!профиль|!профіль", "Профіль"),
            ("/language", "Вибір мови бота"),
            ("/set_name|!лисичка", "Змінити нікнейм"),
            ("/name|!ник|!кличка", "Подивитись на нікнейм"),
            ("/toggle|!приветствие|!привітання", "Включити/Виключити привітання нових користувачів" ),
            ("!обнять", "Відправте в відповідь користувачу щоб його обняти"),
            # Додайте інші команди свого бота тут
        ]
        
        translated_commands_list = [
            (translate_text(language, command[0]), translate_text(language, command[1])) for command in commands_list
        ]
        
        help_text = '\n\n'.join([f'{command[0]} - {command[1]}' for command in translated_commands_list])
        await message.answer(f'{translated_help_text}\n\n{help_text}')
    except Exception as e:
        logging.error("Problem command HELP", exc_info=True)    


conn.commit()
def update_user_nickname(user_id, new_nickname):
    cursor.execute('UPDATE users SET nickname = ? WHERE id = ?', (new_nickname, user_id))
    conn.commit()
    print(f"Nickname for user_id {user_id} updated to {new_nickname}")

class YourStateName(StatesGroup):
    new_name = State()
   
def starts_with_name_command(text):
    lower_text = text.lower()
    return any(lower_text.startswith(prefix) for prefix in ('/set_name', '!лисичка'))


def update_user_nickname(user_id, new_nickname):
    cursor.execute('UPDATE users SET nickname = ? WHERE id = ?', (new_nickname, user_id))
    conn.commit()
    print(f"Nickname for user_id {user_id} updated to {new_nickname}")

@dp.message_handler(lambda message: starts_with_name_command(message.text))
async def set_name_command_new(message: types.Message):
    try:    
        user_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = message.chat.title or message.chat.username or message.chat.first_name

        
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
        

        # Розбиваємо повідомлення на дві частини: команду і аргументи після команди
        parts = message.text.split(maxsplit=1)
        command = parts[0].lower()

        # Якщо є аргументи після команди
        if len(parts) > 1:
            new_nickname = parts[1].strip()

            if "@" in new_nickname:
                await message.reply(translate_text(language, "В нікнеймі не можна використовувати символ '@'."))
            elif len(new_nickname) > 15:
                await message.reply(translate_text(language, "Нікнейм повинен бути не більше 15 символів."))
            else:
                # Збереження нового нікнейму в базі даних
                update_user_nickname(user_id, new_nickname)
                await message.reply(f'{message.from_user.first_name}, {translate_text(language, "твій нікнейм був успішно змінений на:")} {new_nickname}.')

        else:
            # Якщо аргументів після команди немає
            if command == "!лисичка":
                await message.reply(f'{translate_text(language, "Для зміни нікнейму введіть новий нікнейм після")} !лисичка')
            elif command == "/set_name":
                await message.reply(f'{translate_text(language,"Для зміни нікнейму введіть новий нікнейм після")} /set_name')
    except Exception as e:
        logging.error("Problom command /set_name",exc_info=True)

@dp.message_handler(state=YourStateName.new_name)
async def process_new_name(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        new_nickname = message.text.strip()
        chat_id = message.chat.id
        language = get_chat_language(chat_id)

        # Збереження нового нікнейму в базі даних
        update_user_nickname(user_id, new_nickname)

        await state.finish()
        await message.reply(f'{message.from_user.first_name}, {translate_text(language, "твій нікнейм був успішно змінений на:")} {new_nickname}')

def starts_with_nick_command(text):
    lower_text = text.lower()
    return any(lower_text.startswith(prefix) for prefix in ('/name', '!ник', 'кличка'))

@dp.message_handler(lambda message: starts_with_nick_command(message.text))
async def show_name_command(message: types.Message):
    try:    
        user_id = message.from_user.id
        user_nickname = get_user_nickname(user_id)
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = message.chat.title or message.chat.username or message.chat.first_name
    
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
    
        await message.reply(f'{translate_text(language, "Ваш поточний нікнейм:")} {user_nickname}')
    except Exception as e:
        logging.error("Problem command show_name", exc_info=True)    



def format_timedelta(td):
    days, remainder = divmod(td.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    day_word = "день" if days == 1 else "дні" if 1 < days < 5 else "днів"
    return f"{int(days)} {day_word} {int(hours):02}:{int(minutes):02}:{int(seconds):02}"

# Встановіть час запуску, коли бот стартує
START_TIME = datetime.now()

def information_with_command(text):
    lower_text = text.lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ['/group', '!інформація', '!инфо']
@dp.message_handler(lambda message: information_with_command(message.text))
async def stats(message: types.Message):
    try:    
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        chat_title = message.chat.title or message.chat.username or message.chat.first_name
    
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.id} в чаті '{chat_title}' Використав команду: {message.text}")
    

        # Обчислити час роботи бота без перебоїв
        current_time = datetime.now()
        uptime = current_time - START_TIME 
        formatted_uptime = format_timedelta(uptime)  # Форматування timedelta

        # Отримати використану пам'ять
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # у Мб
            # у Мб

        if message.from_user.id in YOUR_USER_ID:  # Адміністратор
            # Витягнути статистику для адміністратора
            users_count = cursor.execute('SELECT COUNT(DISTINCT id) FROM users').fetchone()[0]
            active_users_count = cursor.execute('SELECT COUNT(DISTINCT id) FROM users WHERE last_active_date > datetime("now", "-7 days")').fetchone()[0]  
            groups_count = cursor.execute('SELECT COUNT(DISTINCT chat_id) FROM users WHERE chat_id < 0').fetchone()[0]
            active_groups_count = cursor.execute('SELECT COUNT(DISTINCT chat_id) FROM users WHERE chat_id < 0 AND last_active_date > datetime("now", "-7 days")').fetchone()[0]  

            await message.reply(f'{translate_text(language, "Кількість користувачів:")} {users_count}\n'
                        f'{translate_text(language, "Кількість активних користувачів:")} {active_users_count}\n'
                        f'{translate_text(language, "Кількість груп:")} {groups_count}\n'
                        f'{translate_text(language, "Кількість активних груп:")} {active_groups_count}\n'
                        f'{translate_text(language, "Час роботи без перебоїв:")} {formatted_uptime}\n'
                        f'{translate_text(language, "Використання памяті:")} {memory_usage:.2f}{translate_text(language,"МБ")}')



        else:  # Звичайний користувач
            # Витягнути загальну статистику
            users_count = cursor.execute('SELECT COUNT(DISTINCT id) FROM users').fetchone()[0]
            groups_count = cursor.execute('SELECT COUNT(DISTINCT chat_id) FROM users WHERE chat_id < 0').fetchone()[0]

            await message.reply(f'{translate_text(language, "Кількість користувачів:")} {users_count}\n'
                                f'{translate_text(language, "Кількість груп:")} {groups_count}\n'
                                f'{translate_text(language, "Час роботи без перебоїв:")}{formatted_uptime}\n'
                                f'{translate_text(language, "Використання памяті:")} {memory_usage:.2f}{translate_text(language,"МБ")}')
    except Exception as e:
        logging.error("Problem command /info",exc_info=True)        

def starts_with_broadcast_command(text):
    return text.lower().startswith('!розсилка')

@dp.message_handler(lambda message: starts_with_broadcast_command(message.text))
async def broadcast_to_groups(message: types.Message):
    try:    
        # Перевірка, чи відправник є власником бота
        if message.from_user.id in YOUR_USER_ID:
            # Витягнути всі унікальні chat_id груп
            group_chat_ids = cursor.execute('SELECT DISTINCT chat_id FROM users WHERE chat_id < 0').fetchall()

            for chat_id in group_chat_ids:
                language = get_chat_language(chat_id[0])
                update_message = translate_text(language, "update_message_key")

                try:
                    print(f"Відправка повідомлення до {chat_id[0]}...")
                    await bot.send_message(chat_id[0], update_message)
                    print(f"Повідомлення успішно відправлено до {chat_id[0]}!")
                    await asyncio.sleep(60)  # Зупинка на 60 секунд перед відправкою наступного повідомлення
                except Exception as e:
                    error_message = f"Помилка при відправці повідомлення до групи {chat_id[0]}: {e}"
                    logging.error(error_message)
                    try:
                        await bot.send_message(YOUR_USER_ID, error_message)  # відправка повідомлення вам у приват про помилку
                    except Exception as err:
                        logging.error(f"Помилка при відправці повідомлення адміністратору: {err}")

            # Відправка повідомлення вам в приватні повідомлення
            await bot.send_message(YOUR_USER_ID, "Розсилка по всім групам завершена!")
        else:
            await message.reply("Ви не маєте доступу до цієї команди!")
    #cursor.execute('''ALTER TABLE users ADD COLUMN language INTEGER DEFAULT 0''')
    #cursor.execute  (''' ALTER TABLE users ADD COLUMN last_active_date TIMESTAMP''')
    #cursor.execute("CREATE TABLE IF NOT EXISTS users_stats (id user_id INTEGER PRIMARY KEY, name TEXT, tail_growth INTEGER)") # Створення таблиці для збереження статистики гравців
    except Exception as e:
        logging.error("problom command !розсилка", exc_info=True)
result = cursor.fetchone()
    




def is_admins(user_id):
    return user_id in YOUR_USER_ID

def reset_tail_timer_for_user(user_id):
    reset_time = datetime.now().strftime('%H:%M:%S')  # Обнулення таймера
    cursor.execute('UPDATE users SET last_growth_time = ? WHERE id = ?', (reset_time, user_id))
    conn.commit()
def reset_user_timer(user_id):
    """Обнулити таймер для користувача"""
    # Встановлюємо поточний час в мінус одну годину, таким чином, коли 
    # користувач намагатиметься знову використовувати команду /tail, 
    # він зможе це зробити одразу
    last_used_time[user_id] = datetime.now() - timedelta(hours=1)

    # Оновлюємо час в базі даних
    reset_time_str = (datetime.now() - timedelta(hours=1)).strftime('%H:%M:%S')
    cursor.execute('UPDATE users SET last_growth_time = ? WHERE id = ?', (reset_time_str, user_id))
    conn.commit()




def get_nickname_from_db(user_id):
    conn = sqlite3.connect('DataBase.sql')
    cursor = conn.cursor()
    cursor.execute("SELECT nickname FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None
def update_last_active_date(user_id):
    current_date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Оновіть формат дати, якщо потрібно

    try:
        cursor.execute('UPDATE users SET last_active_date = ? WHERE id = ?', (current_date_str, user_id))
        conn.commit()
        logging.info("Last active date updated successfully!")
    except Exception as e:
        logging.info(f"Error updating the last active date: {e}")
def is_hug_command(text):
    lower_text = text.lower().split()
    if not lower_text:
        return False
    return lower_text[0] in ['/hug', 'обняти', 'обнять']

@dp.message_handler(lambda message: is_hug_command(message.text))
async def process_hug_command(message: types.Message):
    try:    
        sender_id = message.from_user.id
        chat_id = message.chat.id
        language = get_chat_language(chat_id)
        sender_nickname = get_nickname_from_db(sender_id)
        sender_display_name = sender_nickname or message.from_user.full_name  # змінили на full_name
        chat_title = message.chat.title or message.chat.username or message.chat.first_name
        
        
        logging.info(f"Користувач {message.from_user.full_name} {message.from_user.username} в чаті '{chat_title}' Використав команду: {message.text}")
       

        if message.reply_to_message:
            receiver_id = message.reply_to_message.from_user.id
            receiver_nickname = get_nickname_from_db(receiver_id)
            receiver_display_name = receiver_nickname or message.reply_to_message.from_user.full_name

            self_hug_translations = [
                translate_text(language, "{sender_display_name} відчув одинокість і окутав сам себе хвостиком. Інколи нам всім потрібно трохи самообіймів!"),
                translate_text(language,"{sender_display_name} обіймає сам себе, знаючи, що інколи найкращі обійми - це ті, які ми даємо собі."),
                translate_text(language,"{sender_display_name} згортається у клубочок, окутуючи себе своїм хвостиком. Інколи самообійми - це все, що нам потрібно."),
                translate_text(language, "{sender_display_name} ніжно обіймає сам себе, нагадуючи всім нам про важливість самолюбові."),
                translate_text(language,"Нехай інші говорять, що хочуть, {sender_display_name} знає, що обіймати себе - це теж чудово!"),
                translate_text(language,"{sender_display_name} піклується про свої емоції, окутуючи себе в теплі самообійми.")
            ]
            actions_translations = [
                translate_text(language, "{sender} окутав {receiver} хвостиком, приносячи комфорт."),
                translate_text(language, "{sender} спробував обняти {receiver}, але {receiver} ухилився."),
                translate_text(language, "{sender} обіймав {receiver} так сильно, що майже здавив!"),
                translate_text(language, "{sender} обіймав {receiver}, але {receiver} ловко уник обіймів, використовуючи свій хвостик."),
                translate_text(language, "{receiver} відчув, як хвостик {sender} легко торкнувся його, створюючи атмосферу ніжності."),
                translate_text(language, "{sender} намагався обняти {receiver}, але їх хвостики заплуталися. Сміх і радість!"),
                translate_text(language, "{receiver} відчув ніжне обіймання від {sender} і не міг стримати посмішку."),
                translate_text(language, "{sender} обіймав {receiver} так легко, що це більше схоже на гру хвостиками."),
                translate_text(language, "{sender} намагався обіймати {receiver}, але натомість просто лоскотав його хвостиком."),
                translate_text(language, "{receiver} почувався як у захваті, коли {sender} окутав його своїм пухнастим хвостиком.")
    ]
            update_last_active_date(sender_id)
    # Щоб використовувати ці переклади у відповідях:
            if sender_id == receiver_id:
                    translated_text = random.choice(self_hug_translations)
                    await message.answer(translated_text.format(sender_display_name=sender_display_name))
                    return
            else:
                selected_action = random.choice(actions_translations)
                response = selected_action.format(sender=sender_display_name, receiver=receiver_display_name)
                await message.answer(response)
                update_last_active_date(sender_id)
        else:
            await message.answer(translate_text(language, "Відповідь на повідомлення користувача, якого потрібно обійняти."))
    except Exception as e:
        logging.error("Problem command /hug", exc_info=True)        

# This is just a placeholder function. Replace with your actual method to send a message
async def send_message(message):
    print(message)





# Функція-хендлер для команди адміністратора
@dp.message_handler(commands=['reset'])
async def reset_command(message: types.Message):
    user_id = message.from_user.id
    

    # Перевірте, чи є користувач адміністратором
    if not is_admins(user_id):
        await message.reply("Тільки адміністратор може використовувати цю команду!")
        return

    # Визначте ID користувача, якому потрібно скинути таймер
    target_user_id = message.reply_to_message.from_user.id if message.reply_to_message else None
    if target_user_id:
        reset_user_timer(target_user_id)
        await message.reply(f"Користувач {message.reply_to_message.from_user.full_name} може ще раз виростити хвостик.")
    else:
        await message.reply("Відповідь на повідомлення користувача, якому потрібно скинути таймер.")



# Перевірка результату
if result:
    print("Таблиця 'users' існує.")
else:
    print("Таблиця 'users' не існує.")
conn.commit()# Збереження внесених змін у базу даних

def main():
    
 
    dp.middleware.setup(YourStateName())

asyncio.get_event_loop().create_task(clear_old_logs())
executor.start_polling(dp, skip_updates=True)
