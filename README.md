# Telegram Arabic & Sorani TTS Bot

A Telegram bot that converts text messages into audio:

- Arabic messages use the Iraqi male voice `ar-IQ-BasselNeural`.
- Sorani Kurdish messages use the native Vekol Sorani model.
- `/` and `/ping` expose HTTP health endpoints for monitoring.

## Run locally

This project requires Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token"
python main.py
```

Set `PORT` when the hosting provider supplies one. The Sorani model downloads
automatically from Hugging Face on its first use if `model.onnx` is not already
present.

## Deploying

Run the service with:

```bash
python main.py
```

The service listens on `PORT` (default `8080`) and uses `/ping` as its health
check. Keep `TELEGRAM_BOT_TOKEN` in the hosting provider's secret/environment
settings; never commit it to the repository.

## Attribution and license

The Sorani voice model is from Vekol by RevgeAI. It is licensed CC-BY-NC 4.0
and is intended for non-commercial use. See [VEKOL_NOTICE.md](VEKOL_NOTICE.md).