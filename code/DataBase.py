"""SQLite storage. Legacy public helpers remain compatible with the game handlers."""

import logging
import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytz

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("BOT_DB_PATH", str(BASE_DIR / "DataBase.sql"))).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
last_used_time = {}
total_tail_growth = {}
user_show_command = {}


def connect():
    connection = sqlite3.connect(str(DB_PATH), timeout=30)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def parse_datetime(value):
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, datetime.min.time())
    elif isinstance(value, (int, float)):
        result = datetime.fromtimestamp(value, timezone.utc)
    else:
        value = str(value).strip()
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                numeric = float(value)
            except ValueError:
                numeric = None
            if numeric is not None:
                try:
                    return (
                        datetime.fromtimestamp(numeric, timezone.utc).replace(
                            tzinfo=None
                        )
                        if numeric > 0
                        else None
                    )
                except (OverflowError, OSError, ValueError):
                    return None
            for fmt in ("%d-%m-%Y %H:%M:%S", "%H:%M:%S"):
                try:
                    result = datetime.strptime(value, fmt)
                    if fmt == "%H:%M:%S":
                        result = datetime.combine(
                            datetime.utcnow().date(), result.time()
                        )
                    break
                except ValueError:
                    continue
            else:
                logging.warning("Ignoring an invalid legacy timestamp")
                return None
    if result.tzinfo:
        result = result.astimezone(timezone.utc).replace(tzinfo=None)
    return result


def timestamp(value=None):
    return (parse_datetime(value) or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")


def backup_database(destination=None):
    directory = DB_PATH.parent / "db_backups"
    directory.mkdir(exist_ok=True)
    path = (
        Path(destination)
        if destination
        else directory / (datetime.utcnow().strftime("%Y%m%dT%H%M%S%f") + ".sqlite3")
    )
    with sqlite3.connect(str(path)) as target:
        conn.backup(target)
    return path


def create_new_tables():
    """Additive, repeatable migration; never replace existing user rows."""
    existed = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users' COLLATE NOCASE"
    ).fetchone()
    if existed:
        columns = {r[1].lower() for r in conn.execute("PRAGMA table_info(users)")}
        expected = {
            "id",
            "name",
            "total_tail_growth",
            "last_growth_time",
            "last_active_date",
            "dayli_predict_time",
            "nickname",
            "chat_id",
            "language",
            "teeth_count",
            "daily_tail_loss",
            "last_loss_date",
            "rank",
        }
        if not expected.issubset(columns):
            backup_database()
    with conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS Chats (chat_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'ru', number_of_players INTEGER DEFAULT 0)"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
        definitions = {
            "name": "TEXT",
            "total_tail_growth": "REAL DEFAULT 0",
            "last_growth_time": "TEXT",
            "last_active_date": "TEXT",
            "dayli_predict_time": "TEXT",
            "nickname": "TEXT",
            "chat_id": "INTEGER",
            "language": "TEXT DEFAULT 'ru'",
            "teeth_count": "INTEGER DEFAULT 0",
            "daily_tail_loss": "REAL DEFAULT 0",
            "last_loss_date": "TEXT",
            "rank": "INTEGER DEFAULT 0",
        }
        columns = {r[1].lower() for r in conn.execute("PRAGMA table_info(users)")}
        for name, definition in definitions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
        chat_columns = {r[1].lower() for r in conn.execute("PRAGMA table_info(Chats)")}
        for name, definition in {
            "language": "TEXT DEFAULT 'ru'",
            "number_of_players": "INTEGER DEFAULT 0",
        }.items():
            if name not in chat_columns:
                conn.execute(f"ALTER TABLE Chats ADD COLUMN {name} {definition}")
        conn.execute("""CREATE TABLE IF NOT EXISTS UserChats (
            user_id INTEGER, chat_id INTEGER, PRIMARY KEY(user_id, chat_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(chat_id) REFERENCES Chats(chat_id) ON DELETE CASCADE)""")
        for user_id, raw_chat in conn.execute(
            "SELECT id,chat_id FROM users WHERE chat_id IS NOT NULL"
        ).fetchall():
            try:
                normalized_chat = int(raw_chat)
                if str(normalized_chat) != str(raw_chat).strip():
                    raise ValueError("Not an integer chat ID")
            except (ValueError, TypeError, OverflowError):
                # The pre-migration backup retains the exact malformed legacy field.
                normalized_chat = 0
            if not normalized_chat:
                conn.execute("UPDATE users SET chat_id=NULL WHERE id=?", (user_id,))
        # Preserve legacy chat assignments, including when an old DB has dangling references.
        conn.execute(
            "INSERT OR IGNORE INTO Chats(chat_id) SELECT DISTINCT chat_id FROM users WHERE chat_id IS NOT NULL AND chat_id != 0"
        )
        conn.execute(
            "INSERT OR IGNORE INTO UserChats(user_id,chat_id) SELECT id,chat_id FROM users WHERE chat_id IS NOT NULL AND chat_id != 0"
        )
        conn.execute(
            "DELETE FROM UserChats WHERE user_id NOT IN (SELECT id FROM users)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO Chats(chat_id) SELECT DISTINCT chat_id FROM UserChats"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_userchats_chat ON UserChats(chat_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_active ON users(last_active_date)"
        )
        for user_id, active, growth in conn.execute(
            "SELECT id,last_active_date,last_growth_time FROM users"
        ).fetchall():
            # Unknown legacy activity gets a grace period, never immediate deletion.
            normalized = (
                parse_datetime(active) or parse_datetime(growth) or datetime.utcnow()
            )
            conn.execute(
                "UPDATE users SET last_active_date=? WHERE id=?",
                (timestamp(normalized), user_id),
            )
        conn.execute(
            "UPDATE users SET total_tail_growth=COALESCE(total_tail_growth,0), teeth_count=MAX(0,COALESCE(teeth_count,0)), daily_tail_loss=COALESCE(daily_tail_loss,0)"
        )
        conn.execute(
            "UPDATE Chats SET language='ru' WHERE language IS NULL OR language NOT IN ('ru','ua','en','by')"
        )
        conn.execute(
            "UPDATE users SET language='ru' WHERE language IS NULL OR language NOT IN ('ru','ua','en','by')"
        )
        _refresh_counts()


def _refresh_counts():
    conn.execute(
        "UPDATE Chats SET number_of_players=(SELECT COUNT(*) FROM UserChats WHERE UserChats.chat_id=Chats.chat_id)"
    )


conn = connect()
conn.execute("PRAGMA journal_mode=WAL")
cursor = conn.cursor()  # compatibility for existing synchronous handler queries
create_new_tables()


def add_user_to_db(user_id, full_name=None, current_time_for_db=None):
    with conn:
        conn.execute(
            """INSERT INTO users(id,name,last_active_date) VALUES(?,?,?)
            ON CONFLICT(id) DO UPDATE SET name=COALESCE(excluded.name,users.name),
            last_active_date=excluded.last_active_date""",
            (user_id, full_name, timestamp(current_time_for_db)),
        )


def record_activity(user_id, full_name, chat_id=None, now=None):
    with conn:
        conn.execute(
            """INSERT INTO users(id,name,last_active_date) VALUES(?,?,?)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name,last_active_date=excluded.last_active_date""",
            (user_id, full_name, timestamp(now)),
        )
        if chat_id is not None:
            conn.execute("INSERT OR IGNORE INTO Chats(chat_id) VALUES(?)", (chat_id,))
            conn.execute(
                "INSERT OR IGNORE INTO UserChats(user_id,chat_id) VALUES(?,?)",
                (user_id, chat_id),
            )
            conn.execute("UPDATE users SET chat_id=? WHERE id=?", (chat_id, user_id))
            _refresh_counts()


def add_chat_id_to_user(user_id, chat_id):
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(id,last_active_date) VALUES(?,?)",
            (user_id, timestamp()),
        )
        conn.execute("INSERT OR IGNORE INTO Chats(chat_id) VALUES(?)", (chat_id,))
        conn.execute(
            "INSERT OR IGNORE INTO UserChats(user_id,chat_id) VALUES(?,?)",
            (user_id, chat_id),
        )
        conn.execute("UPDATE users SET chat_id=? WHERE id=?", (chat_id, user_id))
        _refresh_counts()


save_user_chat_ids = add_chat_id_to_user
add_chat_id_for_user = add_chat_id_to_user


def get_user_chat_ids(user_id):
    return [
        r[0]
        for r in conn.execute(
            "SELECT chat_id FROM UserChats WHERE user_id=? ORDER BY chat_id", (user_id,)
        )
    ]


def remove_user_from_chat(user_id, chat_id):
    with conn:
        conn.execute(
            "DELETE FROM UserChats WHERE user_id=? AND chat_id=?", (user_id, chat_id)
        )
        conn.execute(
            "UPDATE users SET chat_id=(SELECT chat_id FROM UserChats WHERE user_id=? LIMIT 1) WHERE id=? AND chat_id=?",
            (user_id, user_id, chat_id),
        )
        _refresh_counts()


def _value(user_id, column, default=None):
    row = conn.execute(f"SELECT {column} FROM users WHERE id=?", (user_id,)).fetchone()
    return row[0] if row and row[0] is not None else default


def get_tail_growth(user_id):
    return _value(user_id, "total_tail_growth", 0)


def get_user_teeth(user_id):
    return _value(user_id, "teeth_count", 0)


def get_user_rank(user_id):
    return int(_value(user_id, "rank", 0))


def get_user_nickname(user_id):
    return _value(user_id, "nickname")


def get_user_full_name(user_id):
    return _value(user_id, "name", "Unknown user")


def get_user_first_name(user_id):
    return _value(user_id, "name")


def get_user_nickname_or_name(user_id):
    return get_user_nickname(user_id) or get_user_full_name(user_id)


def user_exists(user_id):
    return (
        conn.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone()
        is not None
    )


get_nickname_from_db = get_user_nickname
get_current_teeth = get_user_teeth
get_user_tail_growth = get_tail_growth
is_user_in_db = user_exists


def update_tail_growth(user_id, new_growth):
    with conn:
        conn.execute(
            "UPDATE users SET total_tail_growth=?,rank=? WHERE id=?",
            (round(new_growth, 1), get_numeric_rank_by_tail_size(new_growth), user_id),
        )


def insert_user_data(user_id, chat_id, nickname, tail_growth):
    add_user_to_db(user_id, nickname)
    add_chat_id_to_user(user_id, chat_id)
    update_user_nickname(user_id, nickname)
    update_tail_growth(user_id, tail_growth)


def update_user_nickname(user_id, new_nickname):
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(id,last_active_date) VALUES(?,?)",
            (user_id, timestamp()),
        )
        conn.execute("UPDATE users SET nickname=? WHERE id=?", (new_nickname, user_id))


def update_last_active_date(user_id):
    with conn:
        conn.execute(
            "UPDATE users SET last_active_date=? WHERE id=?", (timestamp(), user_id)
        )


def load_last_used_times():
    last_used_time.clear()
    for user_id, value in conn.execute("SELECT id,last_growth_time FROM users"):
        parsed = parse_datetime(value)
        if parsed:
            last_used_time[user_id] = parsed
    return last_used_time


def reset_user_timer(user_id):
    value = datetime.utcnow() - timedelta(hours=1)
    with conn:
        conn.execute(
            "UPDATE users SET last_growth_time=? WHERE id=?",
            (timestamp(value), user_id),
        )
    last_used_time[user_id] = value


reset_tail_timer_for_user = reset_user_timer


def get_top_all_chats_users():
    return conn.execute(
        "SELECT id,name,total_tail_growth FROM users ORDER BY total_tail_growth DESC,id LIMIT 15"
    ).fetchall()


def get_top_chat_users(chat_id):
    return conn.execute(
        """SELECT u.id,u.nickname,u.name,u.total_tail_growth FROM users u
        JOIN UserChats uc ON uc.user_id=u.id WHERE uc.chat_id=? AND u.total_tail_growth>0
        ORDER BY u.total_tail_growth DESC,u.id LIMIT 15""",
        (chat_id,),
    ).fetchall()


def get_top_ranks_users():
    return conn.execute(
        "SELECT id,nickname,name,rank,total_tail_growth FROM users WHERE rank>0 ORDER BY rank DESC,total_tail_growth DESC,id LIMIT 10"
    ).fetchall()


def update_all_chats_players_count():
    with conn:
        _refresh_counts()


def get_user_data(user_id):
    row = conn.execute(
        "SELECT teeth_count,total_tail_growth,last_loss_date,daily_tail_loss FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(
        teeth_count=row[0],
        total_tail_growth=row[1],
        last_loss_date=parse_datetime(row[2]) or datetime.min,
        daily_tail_loss=row[3] or 0,
    )


def update_user_data(user_id, data):
    allowed = {"teeth_count", "total_tail_growth", "last_loss_date", "daily_tail_loss"}
    with conn:
        for key, value in data.items():
            if key not in allowed:
                continue
            if key == "last_loss_date":
                value = timestamp(value)
            if key in ("teeth_count", "daily_tail_loss"):
                value = max(0, value)
            conn.execute(f"UPDATE users SET {key}=? WHERE id=?", (value, user_id))
        if "total_tail_growth" in data:
            conn.execute(
                "UPDATE users SET rank=? WHERE id=?",
                (get_numeric_rank_by_tail_size(data["total_tail_growth"]), user_id),
            )


async def update_teeth_count(user_id, new_teeth_count):
    update_user_data(user_id, {"teeth_count": new_teeth_count})


async def update_total_tail_growth(user_id, new_tail_length):
    update_tail_growth(user_id, new_tail_length)


def add_or_remove_teeth(user_id, teeth_amount):
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(id,last_active_date) VALUES(?,?)",
            (user_id, timestamp()),
        )
        conn.execute(
            "UPDATE users SET teeth_count=MAX(0,teeth_count+?) WHERE id=?",
            (teeth_amount, user_id),
        )


def get_numeric_rank_by_tail_size(tail_size):
    try:
        size = float(tail_size)
    except (ValueError, TypeError):
        return 0
    return sum(
        size >= threshold
        for threshold in (100, 500, 800, 1200, 1600, 2000, 2400, 2800, 3500, 5000)
    )


def update_rank_based_on_tail_size(tail_size, user_id):
    new_rank = get_numeric_rank_by_tail_size(tail_size)
    if new_rank == get_user_rank(user_id):
        return None
    with conn:
        conn.execute("UPDATE users SET rank=? WHERE id=?", (new_rank, user_id))
    return new_rank


def reset_daily_tail_lost():
    with conn:
        conn.execute("UPDATE users SET daily_tail_loss=0,last_loss_date=NULL")


def grow_tail(user_id, delta, now=None):
    """Cooldown and score update are a single SQLite transaction."""
    now = parse_datetime(now) or datetime.utcnow()
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT last_growth_time,total_tail_growth FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise ValueError("User must be registered before growing")
        previous = parse_datetime(row[0])
        remaining = timedelta(hours=1) - (now - previous) if previous else timedelta(0)
        if remaining.total_seconds() > 0:
            return False, remaining, row[1]
        total = round((row[1] or 0) + delta, 1)
        conn.execute(
            "UPDATE users SET last_growth_time=?,total_tail_growth=?,last_active_date=? WHERE id=?",
            (timestamp(now), total, timestamp(now), user_id),
        )
    last_used_time[user_id] = now
    return True, timedelta(0), total


def apply_bite(attacker_id, victim_id, success, teeth_loss=1, tail_loss=0, now=None):
    if attacker_id == victim_id:
        raise ValueError("Cannot bite yourself")
    now = parse_datetime(now) or datetime.utcnow()
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        attacker = get_user_data(attacker_id)
        victim = get_user_data(victim_id)
        if not attacker or not victim:
            return {"error": "missing_user"}
        if victim["total_tail_growth"] < 100:
            return {"error": "short_tail"}
        if attacker["teeth_count"] <= 0:
            return {"error": "no_teeth"}
        daily = (
            victim["daily_tail_loss"]
            if victim["last_loss_date"].date() == now.date()
            else 0
        )
        if daily >= 20:
            return {"error": "daily_limit"}
        cost = min(attacker["teeth_count"], max(1, int(teeth_loss))) if success else 1
        loss = min(max(0, float(tail_loss)), 20 - daily) if success else 0
        conn.execute(
            "UPDATE users SET teeth_count=teeth_count-? WHERE id=?", (cost, attacker_id)
        )
        if success:
            total = round(victim["total_tail_growth"] - loss, 1)
            conn.execute(
                "UPDATE users SET total_tail_growth=?,daily_tail_loss=?,last_loss_date=?,rank=? WHERE id=?",
                (
                    total,
                    daily + loss,
                    timestamp(now),
                    get_numeric_rank_by_tail_size(total),
                    victim_id,
                ),
            )
    return {"success": success, "teeth_loss": cost, "tail_loss": loss}


def get_all_chats_from_db():
    return [{"chat_id": r[0]} for r in conn.execute("SELECT chat_id FROM Chats")]


def get_users_in_chat_from_db(chat_id):
    return [
        {"user_id": r[0]}
        for r in conn.execute(
            "SELECT user_id FROM UserChats WHERE chat_id=?", (chat_id,)
        )
    ]


def get_other_chats_for_user_from_db(user_id, excluding_chat_id):
    return [c for c in get_user_chat_ids(user_id) if c != excluding_chat_id]


def delete_user_from_db(user_id):
    with conn:
        conn.execute("DELETE FROM UserChats WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        _refresh_counts()
    last_used_time.pop(user_id, None)


def delete_chat_and_users_from_db(chat_id):
    """Detach a removed chat, preserving player profiles and other memberships."""
    with conn:
        conn.execute("DELETE FROM UserChats WHERE chat_id=?", (chat_id,))
        conn.execute("UPDATE users SET chat_id=NULL WHERE chat_id=?", (chat_id,))
        conn.execute("DELETE FROM Chats WHERE chat_id=?", (chat_id,))
        _refresh_counts()


async def clean_removed_users(chat_id):
    # Membership removal is driven by Telegram events, never by lack of other chats.
    update_all_chats_players_count()


def cleanup_inactive_users(days=180, now=None, dry_run=False):
    if int(days) < 1:
        raise ValueError("days must be positive")
    cutoff = timestamp(
        (parse_datetime(now) or datetime.utcnow()) - timedelta(days=int(days))
    )
    ids = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM users WHERE last_active_date IS NOT NULL AND last_active_date < ?",
            (cutoff,),
        )
    ]
    if dry_run or not ids:
        return ids
    backup_database()  # a recoverable snapshot before destructive housekeeping
    with conn:
        # Re-evaluate under the write lock so newly active users are retained.
        conn.execute("BEGIN IMMEDIATE")
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM users WHERE last_active_date IS NOT NULL AND last_active_date < ?",
                (cutoff,),
            )
        ]
        conn.executemany("DELETE FROM UserChats WHERE user_id=?", ((i,) for i in ids))
        conn.executemany("DELETE FROM users WHERE id=?", ((i,) for i in ids))
        _refresh_counts()
    for i in ids:
        last_used_time.pop(i, None)
    return ids


def get_last_predict_usage(cursor, user_id):
    row = cursor.execute(
        "SELECT dayli_predict_time FROM users WHERE id=?", (user_id,)
    ).fetchone()
    return row[0] if row else None


def set_last_predict_usage(cursor, user_id, timestamp_value):
    cursor.execute(
        "UPDATE users SET dayli_predict_time=? WHERE id=?",
        (timestamp(timestamp_value), user_id),
    )
    cursor.connection.commit()


def claim_prediction(user_id, now=None):
    now = parse_datetime(now) or datetime.utcnow()
    kyiv = pytz.timezone("Europe/Kyiv")
    today = pytz.utc.localize(now).astimezone(kyiv).date()
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT dayli_predict_time FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError("User must be registered")
        previous = parse_datetime(row[0])
        if previous and pytz.utc.localize(previous).astimezone(kyiv).date() >= today:
            return False
        conn.execute(
            "UPDATE users SET dayli_predict_time=? WHERE id=?",
            (timestamp(now), user_id),
        )
    return True


def get_chat_language(chat_id):
    row = conn.execute(
        "SELECT language FROM Chats WHERE chat_id=?", (chat_id,)
    ).fetchone()
    return row[0] if row and row[0] in ("ru", "ua", "en", "by") else "ru"


def get_user_language(user_id):
    value = _value(user_id, "language", "ru")
    return value if value in ("ru", "ua", "en", "by") else "ru"


def set_chat_language(chat_id, language):
    if language not in ("ru", "ua", "en", "by"):
        raise ValueError("Unknown language")
    with conn:
        conn.execute(
            "INSERT INTO Chats(chat_id,language) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET language=excluded.language",
            (chat_id, language),
        )
        if chat_id > 0:
            conn.execute("UPDATE users SET language=? WHERE id=?", (language, chat_id))


# Compatibility for the optional localization module.
class DatabaseFacade:
    get_chat_language = staticmethod(get_chat_language)
    get_user_language = staticmethod(get_user_language)


db = DatabaseFacade()


def migrate_chat(old_chat_id, new_chat_id):
    """Preserve members/settings when Telegram upgrades a group to supergroup."""
    if old_chat_id == new_chat_id:
        return
    with conn:
        language = get_chat_language(old_chat_id)
        conn.execute(
            "INSERT OR IGNORE INTO Chats(chat_id,language) VALUES(?,?)",
            (new_chat_id, language),
        )
        conn.execute(
            "INSERT OR IGNORE INTO UserChats(user_id,chat_id) SELECT user_id,? FROM UserChats WHERE chat_id=?",
            (new_chat_id, old_chat_id),
        )
        conn.execute(
            "UPDATE users SET chat_id=? WHERE chat_id=?", (new_chat_id, old_chat_id)
        )
        conn.execute("DELETE FROM UserChats WHERE chat_id=?", (old_chat_id,))
        conn.execute("DELETE FROM Chats WHERE chat_id=?", (old_chat_id,))
        _refresh_counts()
