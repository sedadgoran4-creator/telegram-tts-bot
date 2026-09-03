# Telegram Multilingual Speech Bot

A Telegram bot with two-way speech support:

- Arabic messages use the Iraqi male voice `ar-IQ-BasselNeural`.
- Sorani Kurdish messages use the native Vekol Sorani model.
- Voice and audio messages are transcribed with multilingual Whisper.
- Whisper automatically detects Kurdish dialects, Arabic, English, and mixed speech.
- `/` and `/ping` expose HTTP health endpoints for monitoring.

## Run locally or on Zeabur

This project requires Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token"
python main.py
```

The `Procfile` starts the same service with Gunicorn on `0.0.0.0` and
`PORT` (default `8080`). The Sorani model downloads automatically from
Hugging Face on its first use if `model.onnx` is not already present. The
Whisper model also downloads automatically from Hugging Face the first time the
bot receives a voice message. `WHISPER_MODEL_SIZE` defaults to `small` for
better multilingual accuracy; set it to `base` on a low-memory host.

## PythonAnywhere

1. Create a Python 3.13 web app.
2. Clone this repository into the PythonAnywhere account.
3. Install dependencies in the web app virtualenv:

```bash
pip install -r requirements.txt
```

4. Add `TELEGRAM_BOT_TOKEN` to the web app environment.
5. Set the WSGI file to this repository's `wsgi.py`.
6. (Optional) Add `WHISPER_MODEL_SIZE=base` if the account has limited memory.
7. Reload the web app.

`wsgi.py` exposes the Flask app and starts one Telegram polling thread. The
health URL is `/ping`.

Send a voice message or audio file to receive its written transcription. Send
Arabic, Kurdish, or English text to receive audio as before.

## Zeabur

Import this GitHub repository, set `TELEGRAM_BOT_TOKEN` as a secret, and let
Zeabur use the included `Procfile`. It starts one Gunicorn worker and listens
on `PORT` (or `8080` when no port is supplied).

Keep `TELEGRAM_BOT_TOKEN` in the hosting provider's secret/environment
settings; never commit it to the repository.

## Important free-tier limits

The code is free-tier compatible, but hosting uptime depends on the provider:
PythonAnywhere's free account has restricted outbound Internet access and does
not provide always-on background tasks. Zeabur's Free Plan auto-sleeps idle
services. Neither provider guarantees a 24/7 Telegram polling process on its
free plan.

## Attribution and license

The Sorani voice model is from Vekol by RevgeAI. It is licensed CC-BY-NC 4.0
and is intended for non-commercial use. See [VEKOL_NOTICE.md](VEKOL_NOTICE.md).