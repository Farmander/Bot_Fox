"""Regression suite: temporary databases, synthetic credentials, no external API calls."""

import asyncio
from datetime import datetime, timedelta
import importlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import logging

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
RUNTIME = tempfile.TemporaryDirectory(prefix="fox-tests-")
os.environ.update(
    BOT_TOKEN="123456789:" + "A" * 35,
    API_KEY="test-key",
    BOT_DB_PATH=str(Path(RUNTIME.name) / "users.sqlite3"),
    ADS_DB_PATH=str(Path(RUNTIME.name) / "ads.sqlite3"),
    LOG_FILENAME=str(Path(RUNTIME.name) / "tests.log"),
)
import Main
import DataBase as db
import ads
import handlers
import loader
import language
from aiogram import types
from aiogram.bot import Bot
from aiogram.dispatcher import Dispatcher


def message(text="/tail", user_id=100, chat_id=-100, message_id=1, **extra):
    data = {
        "message_id": message_id,
        "date": int(datetime.now().timestamp()),
        "from": {"id": user_id, "is_bot": False, "first_name": "Test <Fox>"},
        "chat": {"id": chat_id, "type": "private" if chat_id > 0 else "supergroup"},
        "text": text,
    }
    data.update(extra)
    return types.Message.to_object(data)


def callback(data, user_id, chat_id, message_id):
    return types.CallbackQuery.to_object(
        {
            "id": f"cb-{message_id}",
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "chat_instance": "test",
            "data": data,
            "message": message("ad", user_id, chat_id, message_id).to_python(),
        }
    )


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        with db.conn:
            db.conn.execute("DELETE FROM UserChats")
            db.conn.execute("DELETE FROM users")
            db.conn.execute("DELETE FROM Chats")
        db.last_used_time.clear()

    def test_register_updates_name_activity_preserves_scores(self):
        db.record_activity(1, "Old", -10, datetime(2024, 1, 1))
        db.update_tail_growth(1, 120)
        db.add_or_remove_teeth(1, 3)
        db.update_user_nickname(1, "Fox")
        db.record_activity(1, "New", -10, datetime(2025, 1, 1))
        self.assertEqual(db.get_user_full_name(1), "New")
        self.assertEqual(db.get_tail_growth(1), 120)
        self.assertEqual(db.get_user_nickname(1), "Fox")
        self.assertEqual(db.get_user_teeth(1), 3)
        self.assertEqual(db._value(1, "last_active_date"), "2025-01-01 00:00:00")
        self.assertEqual(
            db.conn.execute("SELECT COUNT(*) FROM UserChats").fetchone()[0], 1
        )

    def test_multiple_chats_count_and_remove_one(self):
        db.record_activity(1, "Fox", -10)
        db.add_chat_id_to_user(1, -20)
        db.add_chat_id_to_user(1, -20)
        self.assertEqual(db.get_user_chat_ids(1), [-20, -10])
        db.remove_user_from_chat(1, -10)
        self.assertTrue(db.user_exists(1))
        self.assertEqual(db.get_user_chat_ids(1), [-20])
        self.assertEqual(
            db.conn.execute(
                "SELECT number_of_players FROM Chats WHERE chat_id=-10"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(db.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_removed_chat_preserves_profiles(self):
        db.record_activity(1, "Fox", -10)
        db.add_chat_id_to_user(1, -20)
        db.delete_chat_and_users_from_db(-10)
        self.assertTrue(db.user_exists(1))
        self.assertEqual(db.get_user_chat_ids(1), [-20])
        self.assertEqual(db.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_group_upgrade_preserves_settings_and_members(self):
        db.record_activity(1, "Fox", -10)
        db.set_chat_language(-10, "en")
        db.migrate_chat(-10, -10010)
        self.assertEqual(db.get_user_chat_ids(1), [-10010])
        self.assertEqual(db.get_chat_language(-10010), "en")
        self.assertEqual(db.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_cleanup_dry_run_boundary_and_backup(self):
        now = datetime(2026, 10, 18, 12)
        db.record_activity(1, "Old", -10, now - timedelta(days=181))
        db.record_activity(2, "Boundary", -10, now - timedelta(days=180))
        db.record_activity(3, "Active", -10, now)
        self.assertEqual(db.cleanup_inactive_users(180, now, dry_run=True), [1])
        self.assertTrue(db.user_exists(1))
        self.assertEqual(db.cleanup_inactive_users(180, now), [1])
        self.assertFalse(db.user_exists(1))
        self.assertTrue(db.user_exists(2))
        self.assertTrue(db.user_exists(3))
        backups = list((db.DB_PATH.parent / "db_backups").glob("*.sqlite3"))
        self.assertTrue(backups)
        with sqlite3.connect(str(max(backups))) as backup:
            self.assertIsNotNone(
                backup.execute("SELECT id FROM users WHERE id=1").fetchone()
            )
        self.assertEqual(
            db.conn.execute(
                "SELECT number_of_players FROM Chats WHERE chat_id=-10"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(db.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_activity_prevents_cleanup(self):
        db.record_activity(1, "Old", -10, datetime.utcnow() - timedelta(days=365))
        db.record_activity(1, "Active", -10)
        self.assertEqual(db.cleanup_inactive_users(dry_run=True), [])

    def test_unknown_legacy_activity_grace(self):
        db.add_user_to_db(1, "Unknown")
        with db.conn:
            db.conn.execute(
                "UPDATE users SET last_active_date=NULL,last_growth_time=0 WHERE id=1"
            )
        db.create_new_tables()
        self.assertEqual(db.cleanup_inactive_users(dry_run=True), [])

    def test_growth_cooldown_atomic_and_persistent(self):
        db.record_activity(1, "Fox", -10)
        now = datetime(2026, 10, 18, 10)
        self.assertTrue(db.grow_tail(1, 5, now)[0])
        self.assertFalse(db.grow_tail(1, 9, now + timedelta(minutes=59))[0])
        self.assertEqual(db.get_tail_growth(1), 5)
        with db.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT total_tail_growth FROM users WHERE id=1"
                ).fetchone()[0],
                5,
            )
        self.assertTrue(db.grow_tail(1, -2, now + timedelta(hours=1))[0])
        self.assertEqual(db.get_tail_growth(1), 3)

    def test_recent_numeric_string_timestamp_enforces_cooldown(self):
        db.add_user_to_db(1, "Fox")
        now = datetime(2026, 10, 18, 12)
        raw = str(
            (now - timedelta(minutes=10))
            .replace(tzinfo=__import__("datetime").timezone.utc)
            .timestamp()
        )
        with db.conn:
            db.conn.execute("UPDATE users SET last_growth_time=? WHERE id=1", (raw,))
        self.assertFalse(db.grow_tail(1, 1, now)[0])

    def test_exception_logs_redact_tokens(self):
        from Log import SecretFormatter

        token = os.environ["BOT_TOKEN"]
        try:
            raise ValueError("credential " + token)
        except ValueError:
            record = logging.LogRecord(
                "test",
                logging.ERROR,
                "test.py",
                1,
                "failure " + token,
                (),
                sys.exc_info(),
            )
            output = SecretFormatter("%(message)s").format(record)
        self.assertNotIn(token, output)
        self.assertIn("[REDACTED]", output)

    def test_growth_accepts_null_and_legacy_numeric_timestamps(self):
        db.add_user_to_db(1, "Fox")
        with db.conn:
            db.conn.execute(
                "UPDATE users SET last_growth_time=? WHERE id=1",
                (int((datetime.utcnow() - timedelta(hours=2)).timestamp()),),
            )
        self.assertTrue(db.grow_tail(1, 1)[0])

    def test_reset_cooldown(self):
        db.add_user_to_db(1, "Fox")
        db.grow_tail(1, 1)
        db.reset_user_timer(1)
        self.assertTrue(db.grow_tail(1, 1)[0])

    def test_prediction_kyiv_calendar_and_repetition(self):
        db.add_user_to_db(1, "Fox")
        self.assertTrue(db.claim_prediction(1, datetime(2026, 10, 18, 20, 59)))
        self.assertFalse(db.claim_prediction(1, datetime(2026, 10, 18, 20, 59, 59)))
        self.assertTrue(db.claim_prediction(1, datetime(2026, 10, 18, 21)))
        self.assertFalse(db.claim_prediction(1, datetime(2026, 10, 18, 21, 1)))

    def test_prediction_commits_supplied_connection(self):
        db.add_user_to_db(1, "Fox")
        with db.connect() as connection:
            db.set_last_predict_usage(connection.cursor(), 1, 1760000000)
        self.assertIsNotNone(db.get_last_predict_usage(db.cursor, 1))

    def test_bite_daily_cap_and_growth_cooldown_separate(self):
        db.add_user_to_db(1, "Attacker")
        db.add_user_to_db(2, "Victim")
        db.add_or_remove_teeth(1, 20)
        db.update_tail_growth(2, 1000)
        now = datetime(2026, 10, 18, 10)
        db.grow_tail(2, 1, now)
        before = db._value(2, "last_growth_time")
        for expected in (8, 8, 4):
            result = db.apply_bite(1, 2, True, 1, 8, now)
            self.assertEqual(result["tail_loss"], expected)
        self.assertEqual(db.apply_bite(1, 2, True, 1, 8, now)["error"], "daily_limit")
        self.assertEqual(db._value(2, "last_growth_time"), before)
        self.assertEqual(db.get_user_data(2)["daily_tail_loss"], 20)
        self.assertEqual(
            db.apply_bite(1, 2, True, 1, 8, now + timedelta(days=1))["tail_loss"], 8
        )

    def test_bite_no_teeth_and_missing_player(self):
        db.add_user_to_db(1, "Attacker")
        db.add_user_to_db(2, "Victim")
        db.update_tail_growth(2, 200)
        self.assertEqual(db.apply_bite(1, 2, False)["error"], "no_teeth")
        self.assertEqual(db.apply_bite(1, 3, False)["error"], "missing_user")
        self.assertEqual(db.get_user_teeth(1), 0)

    def test_bite_failure_costs_one_tooth_only(self):
        db.add_user_to_db(1, "Attacker")
        db.add_user_to_db(2, "Victim")
        db.add_or_remove_teeth(1, 2)
        db.update_tail_growth(2, 200)
        db.apply_bite(1, 2, False)
        self.assertEqual(db.get_user_teeth(1), 1)
        self.assertEqual(db.get_tail_growth(2), 200)

    def test_user_data_loss_date_does_not_overwrite_growth(self):
        db.add_user_to_db(1, "Fox")
        db.grow_tail(1, 1, datetime(2026, 10, 18, 12))
        before = db._value(1, "last_growth_time")
        db.update_user_data(
            1, {"daily_tail_loss": 4, "last_loss_date": datetime(2026, 10, 18)}
        )
        self.assertEqual(db._value(1, "last_growth_time"), before)
        self.assertEqual(db.get_user_data(1)["daily_tail_loss"], 4)

    def test_rank_boundaries(self):
        self.assertEqual(
            [
                db.get_numeric_rank_by_tail_size(n)
                for n in (0, 99.9, 100, 499.9, 500, 4999, 5000)
            ],
            [0, 0, 1, 1, 2, 9, 10],
        )

    def test_scheduler_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(
                os.environ,
                BOT_DB_PATH=str(Path(tmp) / "db.sqlite3"),
                ADS_DB_PATH=str(Path(tmp) / "ads.sqlite3"),
                PYTHONPATH=str(PROJECT),
            )
            code = """
import asyncio
import loader
async def run():
    assert not loader.scheduler.running
    await loader.on_start(loader.dp)
    assert loader.scheduler.running
    assert {job.id for job in loader.scheduler.get_jobs()} == {'backup','cleanup'}
    await loader.on_shutdown(loader.dp)
    await asyncio.sleep(0)
    assert not loader.scheduler.running
asyncio.run(run())
"""
            subprocess.run(
                [sys.executable, "-c", code],
                cwd="/tmp",
                env=env,
                check=True,
                capture_output=True,
            )

    def test_maintenance_cli_from_other_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, BOT_DB_PATH=str(Path(tmp) / "db.sqlite3"))
            for args in (["check"], ["cleanup", "--dry-run"], ["backup"]):
                result = subprocess.run(
                    [sys.executable, str(PROJECT / "manage.py")] + args,
                    cwd="/tmp",
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertTrue(result.stdout.strip())
            self.assertTrue(list((Path(tmp) / "db_backups").glob("*.sqlite3")))

    def test_migrate_minimal_legacy_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "legacy.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT,total_tail_growth REAL)"
                )
                connection.execute("INSERT INTO users VALUES(1,'Legacy',123.4)")
            env = dict(os.environ, BOT_DB_PATH=str(database))
            command = [
                sys.executable,
                "-c",
                "import DataBase as d; d.create_new_tables(); assert d.get_tail_growth(1)==123.4; assert d.conn.execute('PRAGMA foreign_key_check').fetchall()==[]",
            ]
            subprocess.run(
                command, cwd=PROJECT, env=env, check=True, capture_output=True
            )
            self.assertTrue(list((Path(tmp) / "db_backups").glob("*.sqlite3")))

    def test_migrate_uploaded_database_preserves_players(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "DataBase.sql"
            shutil.copy2(PROJECT / "DataBase.sql", database)
            with sqlite3.connect(database) as connection:
                before = connection.execute(
                    "SELECT id,name,total_tail_growth,nickname,teeth_count FROM users ORDER BY id"
                ).fetchall()
            env = dict(os.environ, BOT_DB_PATH=str(database))
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import DataBase as d; d.create_new_tables(); assert d.conn.execute('PRAGMA foreign_key_check').fetchall()==[]",
                ],
                cwd="/tmp",
                env=dict(env, PYTHONPATH=str(PROJECT)),
                check=True,
                capture_output=True,
            )
            with sqlite3.connect(database) as connection:
                after = connection.execute(
                    "SELECT id,name,total_tail_growth,nickname,teeth_count FROM users ORDER BY id"
                ).fetchall()
            self.assertEqual(before, after)


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Bot.set_current(loader.bot)
        Dispatcher.set_current(loader.dp)
        loader.bot._me = types.User(
            id=123456789, is_bot=True, first_name="TestBot", username="TestFoxBot"
        )
        with db.conn:
            db.conn.execute("DELETE FROM UserChats")
            db.conn.execute("DELETE FROM users")
            db.conn.execute("DELETE FROM Chats")
        with ads._connect() as connection:
            for table in ("ad_deliveries", "ad_user_log", "ad_campaigns", "ad_claims"):
                connection.execute(f"DELETE FROM {table}")
        ads._set_ads_enabled(True)
        await loader.storage.reset_state(chat=100, user=100, with_data=True)
        self.sent = []
        self.next_id = 1000

        async def send(chat_id, text, **kwargs):
            await asyncio.sleep(0)
            self.next_id += 1
            self.sent.append((chat_id, text, kwargs))
            return message(text, 100, chat_id, self.next_id)

        self.send = AsyncMock(side_effect=send)
        self.patches = [
            patch.object(loader.bot, "send_message", self.send),
            patch.object(loader.bot, "get_me", AsyncMock(return_value=loader.bot._me)),
            patch.object(
                loader.bot,
                "request",
                AsyncMock(
                    side_effect=AssertionError("Unexpected Telegram API request")
                ),
            ),
            patch.object(
                loader.bot,
                "get_chat_member",
                AsyncMock(
                    return_value=types.ChatMember(
                        user=loader.bot._me,
                        status="administrator",
                        can_delete_messages=True,
                    )
                ),
            ),
            patch.object(
                loader.bot, "answer_callback_query", AsyncMock(return_value=True)
            ),
            patch.object(loader.bot, "edit_message_text", AsyncMock(return_value=True)),
            patch.object(
                loader.bot, "edit_message_reply_markup", AsyncMock(return_value=True)
            ),
            patch.object(loader.bot, "delete_message", AsyncMock(return_value=True)),
        ]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def add_campaign(
        self, title="Test", body="Advertisement", url="https://example.com"
    ):
        with ads._connect() as connection:
            return connection.execute(
                "INSERT INTO ad_campaigns(title,body,url) VALUES(?,?,?)",
                (title, body, url),
            ).lastrowid

    async def dispatch(self, msg):
        await loader.dp.process_update(
            types.Update(update_id=msg.message_id, message=msg)
        )

    async def test_dispatch_tail_registers_and_cooldown(self):
        with (
            patch.object(handlers, "generate_random_num", return_value=5),
            patch.object(handlers.random, "random", return_value=1),
        ):
            await self.dispatch(message("/tail", 100, -100))
            await self.dispatch(message("/tail", 100, -100, 2))
        self.assertEqual(db.get_tail_growth(100), 5)
        self.assertEqual(db.get_user_chat_ids(100), [-100])
        self.assertEqual(len(self.sent), 2)

    async def test_photo_activity_without_text(self):
        msg = message(
            None,
            100,
            -100,
            photo=[
                {
                    "file_id": "test",
                    "file_unique_id": "unique",
                    "width": 10,
                    "height": 10,
                }
            ],
        )
        await self.dispatch(msg)
        self.assertTrue(db.user_exists(100))
        self.assertEqual(db.get_user_chat_ids(100), [-100])

    async def test_ads_command_reaches_handler_and_admin_config(self):
        admin = ads.YOUR_USER_ID[0]
        await self.dispatch(
            message("/ad_add Title | Body | https://example.com", admin, admin)
        )
        with ads._connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM ad_campaigns").fetchone()[0], 1
            )
        self.assertTrue(any("Объявление добавлено" in text for _, text, _ in self.sent))

    async def test_ads_unauthorized_cannot_write(self):
        await self.dispatch(message("/ad_add Title | Body", 100, 100))
        with ads._connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM ad_campaigns").fetchone()[0], 0
            )

    async def test_ads_once_daily_after_successful_send(self):
        self.add_campaign()
        msg = message("hello", 100, 100)
        await ads.maybe_send_ad(msg)
        await ads.maybe_send_ad(msg)
        self.assertEqual(len(self.sent), 1)
        with ads._connect() as connection:
            self.assertEqual(
                connection.execute("SELECT impressions FROM ad_campaigns").fetchone()[
                    0
                ],
                1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM ad_deliveries").fetchone()[0],
                1,
            )

    async def test_ads_failed_send_does_not_consume_impression_or_cooldown(self):
        self.add_campaign()
        self.send.side_effect = RuntimeError("Simulated delivery failure")
        await ads.maybe_send_ad(message("hello", 100, 100))
        with ads._connect() as connection:
            self.assertEqual(
                connection.execute("SELECT impressions FROM ad_campaigns").fetchone()[
                    0
                ],
                0,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM ad_user_log").fetchone()[0], 0
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM ad_claims").fetchone()[0], 0
            )

    async def test_ads_concurrent_messages_show_once(self):
        self.add_campaign()
        await asyncio.gather(
            *(ads.maybe_send_ad(message("hello", 100, 100, i)) for i in range(10))
        )
        self.assertEqual(len(self.sent), 1)

    async def test_ads_pause_and_groups(self):
        self.add_campaign()
        await ads.maybe_send_ad(message("hello", 100, -100))
        ads._set_ads_enabled(False)
        await ads.maybe_send_ad(message("hello", 100, 100))
        self.assertEqual(len(self.sent), 0)

    async def test_ads_callback_counts_once_and_rejects_other_user(self):
        ad_id = self.add_campaign()
        await ads.maybe_send_ad(message("hello", 100, 100))
        mid = self.next_id
        await ads.ad_click_callback(callback(f"adclick:{ad_id}", 100, 100, mid))
        await ads.ad_click_callback(callback(f"adclick:{ad_id}", 100, 100, mid))
        await ads.ad_click_callback(callback(f"adclick:{ad_id}", 200, 100, mid))
        with ads._connect() as connection:
            self.assertEqual(
                connection.execute("SELECT clicks FROM ad_campaigns").fetchone()[0], 1
            )

    async def test_ads_post_middleware_for_unhandled_message(self):
        self.add_campaign()
        await self.dispatch(message("hello", 100, 100))
        self.assertTrue(any("📣 Реклама" in text for _, text, _ in self.sent))

    async def test_ads_limits_and_urls(self):
        for invalid in (
            "javascript:alert(1)",
            "https://user:pass@example.com",
            "https://example.com/ bad",
        ):
            with self.assertRaises(ValueError):
                ads._safe_url(invalid)
        with self.assertRaises(ValueError):
            ads._ad_text("Title", "😀" * 3000)

    async def test_main_chat_does_not_swallow_ads(self):
        from config import MAIN_CHAT_ID

        admin = ads.YOUR_USER_ID[0]
        await self.dispatch(message("/ad_list", admin, MAIN_CHAT_ID))
        self.assertTrue(self.sent)
        self.assertIn("Объявлений пока нет", self.sent[0][1])

    async def test_startup_import_has_no_scheduler_or_thread(self):
        self.assertFalse(loader.scheduler.running)

    async def test_start_command_html_names_and_no_network(self):
        await self.dispatch(message("/start", 100, 100))
        self.assertTrue(any("Привет" in text for _, text, _ in self.sent))

    async def test_predict_persists_limit(self):
        await self.dispatch(message("/predict", 100, -100))
        await self.dispatch(message("/predict", 100, -100, 2))
        self.assertIsNotNone(db.get_last_predict_usage(db.cursor, 100))
        self.assertEqual(len(self.sent), 2)

    async def test_reset_handler_does_not_register_invalid_middleware(self):
        db.add_user_to_db(100, "Fox")
        db.grow_tail(100, 1)
        admin = ads.YOUR_USER_ID[0]
        reply = message("tail", 100, -100).to_python()
        await self.dispatch(message("reset", admin, -100, reply_to_message=reply))
        self.assertTrue(db.grow_tail(100, 1)[0])

    async def test_command_mention_and_other_bot(self):
        with (
            patch.object(handlers, "generate_random_num", return_value=5),
            patch.object(handlers.random, "random", return_value=1),
        ):
            await self.dispatch(message("/tail@TestFoxBot", 100, -100))
            await self.dispatch(message("/tail@OtherBot", 200, -100, 2))
        self.assertEqual(db.get_tail_growth(100), 5)
        self.assertFalse(db.user_exists(200))

    async def test_language_selection_persists(self):
        await self.dispatch(message("/language", 100, 100))
        await loader.dp.process_update(
            types.Update(
                update_id=2, callback_query=callback("en", 100, 100, self.next_id)
            )
        )
        self.assertEqual(db.get_chat_language(100), "en")
        self.assertEqual(db.get_user_language(100), "en")
        self.assertIn("Language changed to: English", self.sent[-1][1])

    async def test_leave_event_removes_membership_not_profile(self):
        db.record_activity(100, "Fox", -100)
        await self.dispatch(
            message(
                None,
                200,
                -100,
                left_chat_member={"id": 100, "is_bot": False, "first_name": "Fox"},
            )
        )
        self.assertTrue(db.user_exists(100))
        self.assertEqual(db.get_user_chat_ids(100), [])

    async def test_help_basic_command(self):
        await self.dispatch(message("/help", 100, -100))
        self.assertTrue(any("telegra.ph" in text for _, text, _ in self.sent))

    async def test_ad_preview_and_edit(self):
        ad_id = self.add_campaign()
        admin = ads.YOUR_USER_ID[0]
        await self.dispatch(
            message(
                f"/ad_edit {ad_id} | New title | New body | https://example.org",
                admin,
                admin,
            )
        )
        await self.dispatch(message(f"/ad_test {ad_id}", admin, admin, 2))
        with ads._connect() as connection:
            row = connection.execute(
                "SELECT title,impressions FROM ad_campaigns WHERE id=?", (ad_id,)
            ).fetchone()
        self.assertEqual(row["title"], "New title")
        self.assertEqual(row["impressions"], 0)
        self.assertTrue(any("New body" in text for _, text, _ in self.sent))

    async def test_ads_skip_fsm_and_resume_after_finishing(self):
        self.add_campaign()
        state = loader.dp.current_state(chat=100, user=100)
        await state.set_state("YourStateName:new_name")
        await ads.maybe_send_ad(message("hello", 100, 100))
        self.assertEqual(len(self.sent), 0)
        await state.finish()
        await ads.maybe_send_ad(message("hello", 100, 100))
        self.assertEqual(len(self.sent), 1)

    async def test_ads_expired_cooldown_allows_next_delivery(self):
        self.add_campaign()
        msg = message("hello", 100, 100)
        await ads.maybe_send_ad(msg)
        with ads._connect() as connection:
            connection.execute(
                "UPDATE ad_user_log SET last_shown_at=datetime('now','-25 hours')"
            )
        await ads.maybe_send_ad(msg)
        self.assertEqual(len(self.sent), 2)

    async def test_ads_bad_legacy_url_releases_claim(self):
        self.add_campaign(url="invalid")
        await ads.maybe_send_ad(message("hello", 100, 100))
        with ads._connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM ad_claims").fetchone()[0], 0
            )
            self.assertEqual(
                connection.execute("SELECT impressions FROM ad_campaigns").fetchone()[
                    0
                ],
                0,
            )

    async def test_ads_large_list_is_split(self):
        admin = ads.YOUR_USER_ID[0]
        for _ in range(50):
            self.add_campaign(title="Long title " * 20)
        await self.dispatch(message("/ad_list", admin, admin))
        self.assertGreater(len(self.sent), 1)
        self.assertTrue(
            all(len(text.encode("utf-16-le")) // 2 <= 4096 for _, text, _ in self.sent)
        )

    async def test_transient_membership_error_keeps_profile_and_chat(self):
        db.record_activity(100, "Fox", -100)
        from aiogram.utils.exceptions import NetworkError

        with patch.object(
            loader.bot,
            "get_chat_member",
            AsyncMock(side_effect=NetworkError("offline")),
        ):
            await loader.clean_removed_chats()
        self.assertTrue(db.user_exists(100))
        self.assertEqual(db.get_user_chat_ids(100), [-100])

    async def test_top_callback_edits_once(self):
        db.record_activity(100, "Fox", -100)
        db.update_tail_growth(100, 200)
        await handlers.process_top_selection(callback("top_chat:100", 100, -100, 5))
        self.assertEqual(loader.bot.edit_message_text.await_count, 1)
        self.assertEqual(loader.bot.answer_callback_query.await_count, 1)

    async def test_core_translations_and_tail_zero(self):
        self.assertEqual(
            language.translate_text("en", "Кількість користувачів:"), "Users count"
        )
        self.assertEqual(language.get_teeth_ending(2, "ua"), "зуби")
        self.assertEqual(language.get_teeth_ending(2, "by"), "зубы")
        self.assertTrue(handlers.get_tail_response(0, "ru"))


if __name__ == "__main__":
    unittest.main()
