"""Entrypoint: register admin ads commands before general message handlers."""

from loader import dp, executor, on_start, on_shutdown
import ads  # noqa: F401
import handlers  # noqa: F401


def main():
    executor.start_polling(
        dp,
        skip_updates=False,
        on_startup=on_start,
        on_shutdown=on_shutdown,
        allowed_updates=["message", "callback_query", "my_chat_member", "chat_member"],
    )


if __name__ == "__main__":
    main()
