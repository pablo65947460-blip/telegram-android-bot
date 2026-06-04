import logging
import os
from functools import wraps

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from fcm_sender import send_data_message


load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger("android_remote_bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])


def admin_only(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id != ADMIN_CHAT_ID:
            LOGGER.warning("Unauthorized Telegram chat_id=%s", chat_id)
            if update.message:
                await update.message.reply_text("Unauthorized.")
            return
        await handler(update, context)

    return wrapper


def as_int(value: str, name: str, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return parsed


async def send(update: Update, data: dict[str, str]) -> None:
    try:
        message_id = await send_data_message(data)
        await update.message.reply_text(f"Sent {data['command']} ({message_id})")
    except Exception as exc:
        LOGGER.exception("Failed to send FCM command")
        await update.message.reply_text(f"FCM error: {exc}")


@admin_only
async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /app <name>")
        return
    await send(update, {"command": "app", "name": " ".join(context.args)})


@admin_only
async def tap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /tap <x> <y>")
        return
    try:
        x = as_int(context.args[0], "x")
        y = as_int(context.args[1], "y")
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await send(update, {"command": "tap", "x": str(x), "y": str(y)})


@admin_only
async def swipe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 4:
        await update.message.reply_text("Usage: /swipe <x1> <y1> <x2> <y2>")
        return
    try:
        x1 = as_int(context.args[0], "x1")
        y1 = as_int(context.args[1], "y1")
        x2 = as_int(context.args[2], "x2")
        y2 = as_int(context.args[3], "y2")
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await send(update, {
        "command": "swipe",
        "x1": str(x1),
        "y1": str(y1),
        "x2": str(x2),
        "y2": str(y2),
    })


@admin_only
async def type_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /type <text>")
        return
    await send(update, {"command": "type", "text": " ".join(context.args)})


@admin_only
async def simple_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command = update.message.text.split()[0].replace("/", "", 1)
    await send(update, {"command": command})


@admin_only
async def volume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /volume <0-100>")
        return
    try:
        value = as_int(context.args[0], "volume", 0, 100)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await send(update, {"command": "volume", "value": str(value)})


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Telegram handler error", exc_info=context.error)


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("app", app_command))
    app.add_handler(CommandHandler("tap", tap_command))
    app.add_handler(CommandHandler("swipe", swipe_command))
    app.add_handler(CommandHandler("type", type_command))
    app.add_handler(CommandHandler("screenshot", simple_command))
    app.add_handler(CommandHandler("home", simple_command))
    app.add_handler(CommandHandler("back", simple_command))
    app.add_handler(CommandHandler("lock", simple_command))
    app.add_handler(CommandHandler("volume", volume_command))
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

