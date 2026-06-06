import logging
import os
from functools import wraps

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from fcm_sender import send_data_message


load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger("android_remote_bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])

DEVICE_NAMES = {
    1: "Honor JDY-LX3",
    2: "Samsung SM-A715F",
}

APP_BUTTONS = {
    "app_spotify": {"name": "Spotify", "package": "com.spotify.music"},
    "app_tiktok": {"name": "TikTok", "package": "com.zhiliaoapp.musically"},
    "app_facebook": {"name": "Facebook", "package": "com.facebook.katana"},
}


def cargar_tokens() -> dict[int, str]:
    tokens = {}
    if "FCM_DEVICE_TOKEN" in os.environ:
        tokens[1] = os.environ["FCM_DEVICE_TOKEN"]

    i = 2
    while True:
        key = f"FCM_DEVICE_TOKEN_{i}"
        if key not in os.environ:
            break
        tokens[i] = os.environ[key]
        i += 1

    return tokens


TOKENS = cargar_tokens()
seleccion = {}


def admin_only(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat and update.effective_chat.id != ADMIN_CHAT_ID:
            return
        await handler(update, context)

    return wrapper


async def send_command(chat_id: int, data: dict[str, str]) -> str:
    num = seleccion.get(chat_id, 1)
    token = TOKENS.get(num)
    if not token:
        return "No hay token para ese dispositivo."

    try:
        await send_data_message(data, token)
        return f"Enviado: {data['command']} -> {DEVICE_NAMES.get(num, f'Tel{num}')}"
    except Exception as exc:
        LOGGER.exception("Failed to send FCM command")
        return f"Error: {exc}"


async def send_to_all(data: dict[str, str]) -> str:
    results = []
    for num, token in TOKENS.items():
        try:
            await send_data_message(data, token)
            results.append(f"Enviado -> {DEVICE_NAMES.get(num, f'Tel{num}')}")
        except Exception as exc:
            LOGGER.exception("Failed to send FCM command to device %s", num)
            results.append(f"Tel{num}: {exc}")
    return "\n".join(results)


def menu_principal() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Todos los dispositivos", callback_data="todos"),
            InlineKeyboardButton("Seleccionar dispositivo", callback_data="seleccionar"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def menu_dispositivos() -> InlineKeyboardMarkup:
    keyboard = []
    for num in TOKENS:
        nombre = DEVICE_NAMES.get(num, f"Tel{num}")
        keyboard.append([InlineKeyboardButton(nombre, callback_data=f"sel_{num}")])
    keyboard.append([InlineKeyboardButton("Volver", callback_data="volver")])
    return InlineKeyboardMarkup(keyboard)


def menu_control(modo="individual") -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Home", callback_data="cmd_home"),
            InlineKeyboardButton("Back", callback_data="cmd_back"),
        ],
        [
            InlineKeyboardButton("Screenshot", callback_data="cmd_screenshot"),
            InlineKeyboardButton("Bloquear", callback_data="cmd_lock"),
        ],
        [
            InlineKeyboardButton("Vol +", callback_data="cmd_vol_up"),
            InlineKeyboardButton("Vol -", callback_data="cmd_vol_down"),
        ],
        [
            InlineKeyboardButton("Scroll arriba", callback_data="cmd_scroll_up"),
            InlineKeyboardButton("Scroll abajo", callback_data="cmd_scroll_down"),
        ],
        [
            InlineKeyboardButton("Spotify", callback_data="cmd_app_spotify"),
            InlineKeyboardButton("TikTok", callback_data="cmd_app_tiktok"),
            InlineKeyboardButton("Facebook", callback_data="cmd_app_facebook"),
        ],
        [
            InlineKeyboardButton("Volver", callback_data="volver"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Panel de Control Android\n\nSelecciona una opcion:",
        reply_markup=menu_principal(),
    )


@admin_only
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "todos":
        seleccion[chat_id] = "todos"
        await query.edit_message_text(
            "Modo: Todos los dispositivos\nLos comandos se enviaran a todos.",
            reply_markup=menu_control("todos"),
        )
        return

    if data == "seleccionar":
        await query.edit_message_text(
            "Selecciona un dispositivo:",
            reply_markup=menu_dispositivos(),
        )
        return

    if data.startswith("sel_"):
        num = int(data.split("_")[1])
        seleccion[chat_id] = num
        nombre = DEVICE_NAMES.get(num, f"Tel{num}")
        await query.edit_message_text(
            f"Dispositivo seleccionado: {nombre}\n\nElige un comando:",
            reply_markup=menu_control(),
        )
        return

    if data == "volver":
        await query.edit_message_text(
            "Panel de Control Android\n\nSelecciona una opcion:",
            reply_markup=menu_principal(),
        )
        return

    if data.startswith("cmd_"):
        comando = data.replace("cmd_", "", 1)
        modo = seleccion.get(chat_id)

        if comando == "vol_up":
            payload = {"command": "volume", "value": "80"}
        elif comando == "vol_down":
            payload = {"command": "volume", "value": "20"}
        elif comando == "scroll_up":
            payload = {"command": "swipe", "x1": "540", "y1": "300", "x2": "540", "y2": "900"}
        elif comando == "scroll_down":
            payload = {"command": "swipe", "x1": "540", "y1": "900", "x2": "540", "y2": "300"}
        elif comando in APP_BUTTONS:
            app_info = APP_BUTTONS[comando]
            payload = {
                "command": "app",
                "name": app_info["name"],
                "package": app_info["package"],
            }
        else:
            payload = {"command": comando}

        if modo == "todos":
            resultado = await send_to_all(payload)
        else:
            resultado = await send_command(chat_id, payload)

        await query.edit_message_text(
            f"{resultado}\n\nElige otro comando:",
            reply_markup=menu_control(modo),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Telegram handler error", exc_info=context.error)


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
