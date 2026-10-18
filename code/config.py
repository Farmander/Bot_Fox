import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# OS values take precedence; retain all supplied credential files unchanged.
for filename in (".env", "admin.env", ".env.env"):
    load_dotenv(BASE_DIR / filename, override=False)

API_TOKEN = (os.getenv("BOT_TOKEN") or os.getenv("API_TOKEN") or "").strip()
API_KEY = os.getenv("API_KEY", "").strip()


def _ids(name, default):
    raw = os.getenv(name, default)
    return tuple(dict.fromkeys(int(value) for value in re.findall(r"-?\d+", raw)))


ADMIN_ID = int(os.getenv("ADMIN_ID") or (_ids("ADMIN_IDS", "563342022")[0]))
YOUR_USER_ID = tuple(
    dict.fromkeys((ADMIN_ID,) + _ids("ADMIN_IDS", "563342022,6385190888"))
)
FARMANDER_ID = int(os.getenv("FARMANDER_ID", "6385190888"))
MY_CUSTOM_NAME = os.getenv("MY_CUSTOM_NAME", "Анди")
MAIN_CHAT_ID = int(os.getenv("MAIN_CHAT_ID", "1960468434"))
BLOCKED_BOT_IDS = {
    str(i) for i in _ids("BLOCKED_BOT_IDS", "1961946938,5915439168,1705070854")
}
BOBR_ID = _ids("BOBR_IDS", "563342022,560006725")
_log_path = Path(os.getenv("LOG_FILENAME", "Logging.log"))
LOG_FILENAME = str(_log_path if _log_path.is_absolute() else BASE_DIR / _log_path)
INACTIVE_USER_DAYS = int(os.getenv("INACTIVE_USER_DAYS", "180"))
if INACTIVE_USER_DAYS < 1:
    raise RuntimeError("INACTIVE_USER_DAYS должен быть больше нуля")
if not API_TOKEN:
    raise RuntimeError(
        "Укажите BOT_TOKEN или API_TOKEN в admin.env, .env либо переменных окружения."
    )
