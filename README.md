# Telegram Arabic & Sorani TTS Bot

A Telegram bot that converts text messages into audio:

- Arabic messages use the Iraqi male voice `ar-IQ-BasselNeural`.
- Sorani Kurdish messages use the native Vekol Sorani model.
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
Hugging Face on its first use if `model.onnx` is not already present.

## PythonAnywhere

1. Create a Python 3.13 web app.
2. Clone this repository into the PythonAnywhere account.
3. Install dependencies in the web app virtualenv:

```bash
pip install -r requirements.txt
```

4. Add `TELEGRAM_BOT_TOKEN` to the web app environment.
5. Set the WSGI file to this repository's `wsgi.py`.
6. Reload the web app.

`wsgi.py` exposes the Flask app and starts one Telegram polling thread. The
health URL is `/ping`.

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