import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
from dotenv import load_dotenv

# === Настройка среды ===
nest_asyncio.apply()
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://gemad-bot.onrender.com"
MINIAPP_URL = "https://gemad.onrender.com"

# === Flask ===
app = Flask(__name__)

# === Aiogram Bot Application ===
application = Application.builder().token(TOKEN).build()

# === /start handler ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("➡ /start", update.effective_user.id)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open App", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )

    photo_path = "GemAd-logo.jpg"  # убедись, что файл есть рядом с bot.py
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption="🎁 Welcome to GemAd! 🌟 Discover useful deals and earn gifts!",
                reply_markup=keyboard
            )
    else:
        await update.message.reply_text(
            text="🎁 Welcome to GemAd! 🌟 Discover useful deals and earn gifts!",
            reply_markup=keyboard
        )

application.add_handler(CommandHandler("start", start))

# === Setup webhook ===
async def setup():
    await application.initialize()
    await application.start()
    info = await application.bot.get_webhook_info()
    if info.url != WEBHOOK_URL:
        await application.bot.delete_webhook()
        await application.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    else:
        print("🔁 Webhook уже установлен")

# === Flask endpoint ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)

        # Отправляем обработку обновления в глобальный event loop
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return "ok"
    return "Bot is working!"

# === Main ===
if __name__ == "__main__":
    print("🚀 Bot starts...")
    loop = asyncio.get_event_loop()  # глобальный loop
    loop.run_until_complete(setup())
    print("✅ Flask is running...")
    # Render автоматически подставляет PORT
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
