"""Offline maintenance CLI. Run from any working directory using Python 3.11."""

import argparse
import config  # load the same environment files as Main.py
import DataBase as db


def main():
    parser = argparse.ArgumentParser(description="Обслуживание базы Лисёнка")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("backup", help="Создать согласованную резервную копию SQLite")
    clean = sub.add_parser("cleanup", help="Очистить неактивные профили")
    clean.add_argument("--days", type=int, default=config.INACTIVE_USER_DAYS)
    clean.add_argument(
        "--dry-run", action="store_true", help="Только показать количество кандидатов"
    )
    sub.add_parser("check", help="Проверить целостность базы и связей")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            print(f"Резервная копия: {db.backup_database()}")
        elif args.command == "cleanup":
            removed = db.cleanup_inactive_users(args.days, dry_run=args.dry_run)
            print(
                f"{'Кандидатов' if args.dry_run else 'Удалено профилей'}: {len(removed)}"
            )
        else:
            integrity = db.conn.execute("PRAGMA integrity_check").fetchall()
            foreign_keys = db.conn.execute("PRAGMA foreign_key_check").fetchall()
            print(
                f"Целостность: {integrity[0][0]}; нарушений связей: {len(foreign_keys)}"
            )
            if integrity != [("ok",)] or foreign_keys:
                raise SystemExit(1)
    finally:
        db.conn.close()


if __name__ == "__main__":
    main()
