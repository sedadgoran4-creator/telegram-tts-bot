import asyncio
import logging
from io import BytesIO
import os
from pathlib import Path
import tempfile
import time
from threading import Lock, Thread

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
        "Add it as a secret/environment variable before starting the bot."
    )

PORT = int(os.environ.get("PORT", "8080"))
TTS_VOICE = os.environ.get("TTS_VOICE", "ar-IQ-BasselNeural")
TTS_REQUEST_TIMEOUT = 60
TTS_TOTAL_TIMEOUT = 180
TTS_ATTEMPTS = 3
TTS_CONCURRENCY = 1
STT_TOTAL_TIMEOUT = 300
STT_MAX_AUDIO_BYTES = 20 * 1024 * 1024
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
tts_semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
stt_semaphore = asyncio.Semaphore(1)
health_app = Flask(__name__)
_whisper_model = None
_whisper_model_lock = Lock()

KURDISH_MARKERS = frozenset("پچژڕڵۆێەڤگ")


def is_sorani_text(text: str) -> bool:
    """Route Sorani text to the native Kurdish model."""
    return any(character in KURDISH_MARKERS for character in text)


def transcribe_audio_file(audio_path: str) -> tuple[str, str]:
    """Transcribe multilingual audio with Whisper and return text plus language."""
    global _whisper_model

    if _whisper_model is None:
        with _whisper_model_lock:
            if _whisper_model is None:
                from faster_whisper import WhisperModel

                logger.info(
                    "Loading Whisper model %s for multilingual transcription",
                    WHISPER_MODEL_SIZE,
                )
                _whisper_model = WhisperModel(
                    WHISPER_MODEL_SIZE,
                    device="cpu",
                    compute_type="int8",
                )

    segments, info = _whisper_model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    transcript = " ".join(
        segment.text.strip() for segment in segments if segment.text.strip()
    ).strip()
    if not transcript:
        raise RuntimeError("Speech recognition returned no text")
    return transcript, info.language or "unknown"


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


async def voice_to_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Download a Telegram voice/audio message and reply with its transcript."""
    if not update.message:
        return

    voice_or_audio = update.message.voice or update.message.audio
    if not voice_or_audio:
        return

    file_size = getattr(voice_or_audio, "file_size", None)
    if file_size and file_size > STT_MAX_AUDIO_BYTES:
        await update.message.reply_text(
            "ئەم فایلە زۆر گەورەیە. تکایە دەنگێک بنێرە کە لە ٢٠MB کەمتر بێت."
        )
        return

    try:
        telegram_file = await context.bot.get_file(voice_or_audio.file_id)
        audio_bytes = await telegram_file.download_as_bytearray()
        if len(audio_bytes) > STT_MAX_AUDIO_BYTES:
            await update.message.reply_text(
                "ئەم فایلە زۆر گەورەیە. تکایە دەنگێک بنێرە کە لە ٢٠MB کەمتر بێت."
            )
            return

        with tempfile.NamedTemporaryFile(
            suffix=".ogg",
            prefix="telegram-stt-",
            delete=False,
        ) as temporary_audio:
            temporary_audio.write(audio_bytes)
            audio_path = Path(temporary_audio.name)

        try:
            async with stt_semaphore:
                transcript, language = await asyncio.wait_for(
                    asyncio.to_thread(transcribe_audio_file, str(audio_path)),
                    timeout=STT_TOTAL_TIMEOUT,
                )
        finally:
            audio_path.unlink(missing_ok=True)

        await update.message.reply_text(
            f"📝 دەقی دەنگ ({language}):\n\n{transcript}"
        )
    except ModuleNotFoundError:
        logger.exception("Whisper dependency is not installed")
        await update.message.reply_text(
            "پێکهاتەی ناسینەوەی دەنگ لەم سێرڤەرەدا دانەمەزراوە. "
            "تکایە requirements.txt دابمەزرێنە و دووبارە هەوڵ بدە."
        )
    except Exception:
        logger.exception(
            "Speech-to-text failed for chat %s",
            update.effective_chat.id if update.effective_chat else "unknown",
        )
        await update.message.reply_text(
            "نەتوانرا دەنگەکە بکرێتە دەق. تکایە دەنگێکی ڕوونتر بنێرە و دووبارە هەوڵ بدە."
        )


def build_telegram_app():
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
    app.add_handler(
        MessageHandler(
            filters.VOICE | filters.AUDIO,
            voice_to_text,
        )
    )
    return app


def run_bot_forever() -> None:
    """Keep Telegram polling alive and retry after unexpected disconnects."""
    while True:
        try:
            build_telegram_app().run_polling(drop_pending_updates=True)
        except Exception:
            logger.exception("Telegram bot stopped unexpectedly; retrying soon")
            time.sleep(5)


def main() -> None:
    Thread(target=keep_alive, name="health-server", daemon=True).start()
    run_bot_forever()


if __name__ == "__main__":
    main()