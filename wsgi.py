"""PythonAnywhere WSGI entry point.

PythonAnywhere serves `application` with its WSGI server. The Telegram bot is
started once in a daemon thread so the web health endpoints and bot can share
the same process.
"""

from threading import Lock, Thread

from main import health_app, run_bot_forever


_start_lock = Lock()
_bot_thread = None


def start_bot_once() -> None:
    global _bot_thread
    with _start_lock:
        if _bot_thread is None or not _bot_thread.is_alive():
            _bot_thread = Thread(
                target=run_bot_forever,
                name="telegram-bot",
                daemon=True,
            )
            _bot_thread.start()


start_bot_once()
application = health_app