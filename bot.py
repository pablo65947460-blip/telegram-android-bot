import logging
import os
from functools import wraps

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from fcm_sender import send_data_message

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger("android_remote_bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])

# Nombres de dispositivos
DEVICE_NAMES = {
    1: "📱 Honor JDY-LX3",
    2: "📱 Samsung SM-A715F",
}

def cargar_tokens():
    tokens = {}
    if "FCM_DEVICE_TOKEN" in os.environ:
        tokens[1] = os.environ["FCM_DEVICE_TOKEN"]
    i = 2
    while True:
        key = f"FCM_DEVICE_TOKEN_{i}"
        if key in os.environ:
            tokens[i] = os.environ[key]
            i += 1
        else:
            break
    return tokens

TOKENS = cargar_tokens()
seleccion = {}  # chat_id -> numero de dispositivo

def admin_only(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat and update.effective_chat.id != ADMIN_CHAT_ID:
            return
        await handler(update, context)
    return wrapper

async def send_command(chat_id, data):
    num = seleccion.get(chat_id, 1)
    token = TOKENS.get(num)
    if not token:
        return "❌ No hay token"
    try:
        await send_data_message(data, token)
        return f"✅ {data['command']} → {DEVICE_NAMES.get(num, f'Tel{num}')}"
    except Exception as exc:
        return f"❌ Error: {exc}"

async def send_to_all(data):
    results = []
    for num, token in TOKENS.items():
        try:
            await send_data_message(data, token)
            results.append(f"✅ {DEVICE_NAMES.get(num, f'Tel{num}')}")
        except Exception as exc:
            results.append(f"❌ Tel{num}: {exc}")
    return "\n".join(results)

def menu_principal():
    keyboard = [
        [
            InlineKeyboardButton("📱 Todos los dispositivos", callback_data="todos"),
            InlineKeyboardButton("🎯 Seleccionar dispositivo", callback_data="seleccionar"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_dispositivos():
    keyboard = []
    for num, nombre in DEVICE_NAMES.items():
        keyboard.append([InlineKeyboardButton(nombre, callback_data=f"sel_{num}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver")])
    return InlineKeyboardMarkup(keyboard)

def menu_control(modo="individual"):
    keyboard = [
        [
            InlineKeyboardButton("🏠 Home", callback_data="cmd_home"),
            InlineKeyboardButton("⬅️ Back", callback_data="cmd_back"),
        ],
        [
            InlineKeyboardButton("📸 Screenshot", callback_data="cmd_screenshot"),
            InlineKeyboardButton("🔒 Bloquear", callback_data="cmd_lock"),
        ],
        [
            InlineKeyboardButton("🔊 Vol +", callback_data="cmd_vol_up"),
            InlineKeyboardButton("🔉 Vol -", callback_data="cmd_vol_down"),
        ],
        [
            InlineKeyboardButton("⬆️ Scroll arriba", callback_data="cmd_scroll_up"),
            InlineKeyboardButton("⬇️ Scroll abajo", callback_data="cmd_scroll_down"),
        ],
        [
            InlineKeyboardButton("🔙 Volver", callback_data="volver"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎮 *Panel de Control Android*\n\nSelecciona una opción:",
        parse_mode="Markdown",
        reply_markup=menu_principal()
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
            "📱 *Modo: Todos los dispositivos*\nLos comandos se enviarán a todos.",
            parse_mode="Markdown",
            reply_markup=menu_control("todos")
        )

    elif data == "seleccionar":
        await query.edit_message_text(
            "🎯 *Selecciona un dispositivo:*",
            parse_mode="Markdown",
            reply_markup=menu_dispositivos()
        )

    elif data.startswith("sel_"):
        num = int(data.split("_")[1])
        seleccion[chat_id] = num
        nombre = DEVICE_NAMES.get(num, f"Tel{num}")
        await query.edit_message_text(
            f"✅ *Dispositivo seleccionado:* {nombre}\n\nElige un comando:",
            parse_mode="Markdown",
            reply_markup=menu_control()
        )

    elif data == "volver":
        await query.edit_message_text(
            "🎮 *Panel de Control Android*\n\nSelecciona una opción:",
            parse_mode="Markdown",
            reply_markup=menu_principal()
        )

    elif data.startswith("cmd_"):
        comando = data.replace("cmd_", "")
        modo = seleccion.get(chat_id)

        if comando == "vol_up":
            payload = {"command": "volume", "value": "80"}
        elif comando == "vol_down":
            payload = {"command": "volume", "value": "20"}
        elif comando == "scroll_up":
            payload = {"command": "swipe", "x1": "540", "y1": "300", "x2": "540", "y2": "900"}
        elif comando == "scroll_down":
            payload = {"command": "swipe", "x1": "540", "y1": "900", "x2": "540", "y2": "300"}
        else:
            payload = {"command": comando}

        if modo == "todos":
            resultado = await send_to_all(payload)
        else:
            resultado = await send_command(chat_id, payload)

        await query.edit_message_text(
            f"{resultado}\n\nElige otro comando:",
            reply_markup=menu_control(modo)
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
