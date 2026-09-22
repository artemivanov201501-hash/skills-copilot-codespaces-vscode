from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot_logic import SYSTEM_PROMPT, build_analysis_text, build_template_response, sanitize_user_input

load_dotenv()


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
MAX_AUDIO_MB = float(os.getenv("MAX_AUDIO_MB", "20"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Здравствуйте! Я бот поддержки. Отправьте текст или голосовое сообщение, "
        "и я постараюсь бережно ответить."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Поддерживаются текстовые и голосовые сообщения (voice).\n"
        "Команды: /start, /help, /cancel"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Текущее действие отменено. Можете отправить новое сообщение.")


def transcribe_audio(file_path: Path) -> str:
    with file_path.open("rb") as audio_file:
        response = openai_client.audio.transcriptions.create(
            model=OPENAI_TRANSCRIPTION_MODEL,
            file=audio_file,
        )
    return sanitize_user_input(response.text)


def transcribe_audio_with_fallback(file_path: Path) -> str:
    try:
        return transcribe_audio(file_path)
    except Exception as first_error:
        logger.warning("Direct transcription failed, trying ffmpeg conversion: %s", first_error)
        converted = file_path.with_suffix(".wav")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(file_path), str(converted)],
                check=True,
                capture_output=True,
                text=True,
            )
            return transcribe_audio(converted)
        except Exception as conversion_error:
            logger.exception("Transcription failed after conversion")
            raise RuntimeError("transcription_failed") from conversion_error


def generate_analysis(transcribed_text: str) -> str:
    response = openai_client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcribed_text},
        ],
        temperature=0.3,
    )
    content = response.choices[0].message.content if response.choices else ""
    return build_analysis_text(transcribed_text, content or "")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    user_text = sanitize_user_input(message.text or "")
    if not user_text:
        await message.reply_text("Не удалось прочитать текст сообщения. Попробуйте ещё раз.")
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    analysis = generate_analysis(user_text)
    await message.reply_text(build_template_response(user_text, analysis))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    voice = message.voice
    if voice is None:
        await message.reply_text("Голосовое сообщение не найдено. Попробуйте ещё раз.")
        return

    if voice.file_size and (voice.file_size / (1024 * 1024)) > MAX_AUDIO_MB:
        await message.reply_text(
            f"Файл слишком большой. Пожалуйста, отправьте аудио до {MAX_AUDIO_MB:g} МБ."
        )
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    with tempfile.TemporaryDirectory(prefix="tg_voice_") as tmpdir:
        source_path = Path(tmpdir) / "voice.ogg"
        telegram_file = await context.bot.get_file(voice.file_id)
        await telegram_file.download_to_drive(custom_path=str(source_path))

        try:
            transcribed = transcribe_audio_with_fallback(source_path)
        except Exception:
            await message.reply_text(
                "Не удалось распознать голосовое сообщение. Проверьте качество записи и попробуйте ещё раз."
            )
            return

    if not transcribed:
        await message.reply_text("Не удалось получить текст из голосового сообщения.")
        return

    analysis = generate_analysis(transcribed)
    await message.reply_text(build_template_response(transcribed, analysis))


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Сейчас я поддерживаю только текстовые и голосовые сообщения Telegram (voice)."
    )


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(
        MessageHandler(
            (filters.ATTACHMENT | filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO)
            & ~filters.VOICE,
            handle_unsupported,
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()
