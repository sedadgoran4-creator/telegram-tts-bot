import asyncio
import logging
from io import BytesIO
import os
from threading import Thread

from edge_tts import Communicate
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


raw_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TOKEN = "".join(
    character
    for character in raw_token
    if character.isascii() and not character.isspace()
)
if not TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is not configured. "
        "Add it as a Replit Secret before starting the bot."
    )

PORT = int(os.environ.get("PORT", "8080"))
TTS_VOICE = os.environ.get("TTS_VOICE", "ar-IQ-BasselNeural")
TTS_REQUEST_TIMEOUT = 60
TTS_TOTAL_TIMEOUT = 180
TTS_ATTEMPTS = 3
TTS_CONCURRENCY = 1
tts_semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
health_app = Flask(__name__)

KURDISH_MARKERS = frozenset("پچژڕڵۆێەڤگ")


def is_sorani_text(text: str) -> bool:
    """Route Sorani text to the native Kurdish model."""
    return any(character in KURDISH_MARKERS for character in text)


@health_app.get("/")
def health_check():
    return "Bot is running", 200


@health_app.get("/ping")
def ping():
    return "OK", 200


def keep_alive() -> None:
    """Run the health server without blocking Telegram polling."""
    health_app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


async def text_to_speech(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message or not update.message.text:
        return

    user_text = update.message.text

    async def synthesize() -> BytesIO:
        if is_sorani_text(user_text):
            from vekol_tts import speak_to_buffer

            return await asyncio.to_thread(speak_to_buffer, user_text)

        audio_buffer = BytesIO()
        communicate = Communicate(
            text=user_text,
            voice=TTS_VOICE,
            rate="+0%",
            volume="+0%",
            pitch="+0Hz",
            connect_timeout=10,
            receive_timeout=TTS_REQUEST_TIMEOUT,
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        audio_buffer.seek(0)
        if not audio_buffer.getbuffer().nbytes:
            raise RuntimeError("TTS returned no audio")
        return audio_buffer

    async with tts_semaphore:
        audio_buffer = None
        for attempt in range(1, TTS_ATTEMPTS + 1):
            try:
                audio_buffer = await asyncio.wait_for(
                    synthesize(),
                    timeout=TTS_TOTAL_TIMEOUT,
                )
                break
            except Exception:
                logger.exception(
                    "TTS attempt %s/%s failed for chat %s",
                    attempt,
                    TTS_ATTEMPTS,
                    update.effective_chat.id if update.effective_chat else "unknown",
                )
                if attempt < TTS_ATTEMPTS:
                    await asyncio.sleep(attempt * 2)

    if audio_buffer is None:
        try:
            await update.message.reply_text(
                "نەتوانرا دەنگی ئەم نامەیە دروست بکرێت. تکایە دووبارە هەوڵ بدە."
            )
        except Exception:
            logger.exception("Could not send TTS error message")
        return

    try:
        await update.message.reply_audio(
            audio=audio_buffer,
            filename="speech.mp3",
            read_timeout=30,
            write_timeout=30,
            connect_timeout=10,
            pool_timeout=10,
        )
    except Exception:
        logger.exception(
            "Telegram audio reply failed for chat %s",
            update.effective_chat.id if update.effective_chat else "unknown",
        )


def main() -> None:
    Thread(target=keep_alive, name="health-server", daemon=True).start()

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .concurrent_updates(True)
        .connect_timeout(10)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(10)
        .get_updates_connect_timeout(10)
        .get_updates_read_timeout(30)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(10)
        .build()
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_to_speech,
        )
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()