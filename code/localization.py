import json
import logging
from typing import Dict, Any
from DataBase import db, BASE_DIR

logger = logging.getLogger(__name__)


class Localization:
    def __init__(self):
        self.translations: Dict[str, Dict[str, str]] = {}
        self.load_all_translations()

    def load_all_translations(self):
        """Загрузка всех переводов"""
        languages = ["ru", "ua", "en", "by"]
        for lang in languages:
            try:
                with open(BASE_DIR / f"{lang}.json", "r", encoding="utf-8") as f:
                    self.translations[lang] = json.load(f)
            except FileNotFoundError:
                logger.warning(f"Translation file for {lang} not found")
                self.translations[lang] = {}
            except json.JSONDecodeError as e:
                logger.error(f"Error loading {lang}.json: {e}")
                self.translations[lang] = {}

    def get_text(
        self, key: str, chat_id: int = None, user_id: int = None, default: str = None
    ) -> str:
        """Получение переведенного текста"""
        # Определяем язык
        language = "ru"
        if chat_id:
            language = db.get_chat_language(chat_id)

        elif user_id:
            language = db.get_user_language(user_id)

        # Получаем перевод
        lang_dict = self.translations.get(language, self.translations.get("ru", {}))
        text = lang_dict.get(key)

        if text is None and default is not None:
            return default

        return text or key

    def translate_time(self, seconds: int, language: str = "ru") -> str:
        """Перевод времени на нужный язык"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        time_dicts = {
            "ru": {
                "hours": ["час", "часа", "часов"],
                "minutes": ["минута", "минуты", "минут"],
                "seconds": ["секунда", "секунды", "секунд"],
            },
            "ua": {
                "hours": ["година", "години", "годин"],
                "minutes": ["хвилина", "хвилини", "хвилин"],
                "seconds": ["секунда", "секунди", "секунд"],
            },
            "en": {
                "hours": ["hour", "hours", "hours"],
                "minutes": ["minute", "minutes", "minutes"],
                "seconds": ["second", "seconds", "seconds"],
            },
            "by": {
                "hours": ["гадзіна", "гадзіны", "гадзін"],
                "minutes": ["хвіліна", "хвіліны", "хвілін"],
                "seconds": ["секунда", "секунды", "секунд"],
            },
        }

        lang_dict = time_dicts.get(language, time_dicts["ru"])

        def pluralize(num: int, forms: list) -> str:
            if num % 10 == 1 and num % 100 != 11:
                return forms[0]
            elif 2 <= num % 10 <= 4 and (num % 100 < 12 or num % 100 > 14):
                return forms[1]
            else:
                return forms[2]

        parts = []
        if hours > 0:
            parts.append(f"{hours} {pluralize(hours, lang_dict['hours'])}")
        if minutes > 0:
            parts.append(f"{minutes} {pluralize(minutes, lang_dict['minutes'])}")
        if secs > 0 or not parts:
            parts.append(f"{secs} {pluralize(secs, lang_dict['seconds'])}")

        return " ".join(parts)


# Глобальный экземпляр локализации
loc = Localization()
