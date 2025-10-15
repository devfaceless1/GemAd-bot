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
application = Application.builder().token(TOKEN).build()

# === /start handler ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open App", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )
    photo_path = "GemAd-logo.jpg"
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption="🎁 Welcome to GemAd! 🌟",
                reply_markup=keyboard
            )
    else:
        await update.message.reply_text(
            "🎁 Welcome to GemAd! 🌟",
            reply_markup=keyboard
        )

application.add_handler(CommandHandler("start", start))

# === Flask endpoint ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        # Используем основной loop, созданный в __main__
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
        return "ok"
    return "Bot is working!"

# === Main ===
if __name__ == "__main__":
    print("🚀 Bot запускается...")
    # Создаем основной event loop
    main_loop = asyncio.get_event_loop()
    main_loop.run_until_complete(application.initialize())
    main_loop.run_until_complete(application.start())

    # Устанавливаем webhook
    main_loop.run_until_complete(application.bot.set_webhook(WEBHOOK_URL))
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")

    # Запуск Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
