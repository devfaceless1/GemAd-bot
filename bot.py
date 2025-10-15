import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://gemad-bot.onrender.com"
MINIAPP_URL = "https://gemad.onrender.com"

app = Flask(__name__)

# === Создаем Telegram Application ===
application = Application.builder().token(TOKEN).build()

# === Обработчик команды /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 Получена команда /start от {update.effective_user.id}")
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open App 🚀", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )

    photo_path = "GemAd-logo.jpg"
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption="🎁 Welcome to GemAd! 🌟 Discover deals and earn rewards!",
                reply_markup=keyboard,
            )
    else:
        await update.message.reply_text(
            "🎁 Welcome to GemAd! 🌟 Discover deals and earn rewards!",
            reply_markup=keyboard,
        )

# === Регистрируем хэндлер ===
application.add_handler(CommandHandler("start", start))

# === Flask endpoint ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        # Обрабатываем апдейт через основной event loop
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
        return "ok"
    return "Bot is working!"

# === Main ===
if __name__ == "__main__":
    print("🚀 Bot запускается...")

    main_loop = asyncio.get_event_loop()

    async def init():
        await application.initialize()
        await application.start()
        await application.bot.delete_webhook()
        await application.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")

    main_loop.run_until_complete(init())

    print("✅ Flask сервер запущен...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
