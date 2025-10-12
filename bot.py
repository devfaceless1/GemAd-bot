import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://gemad-bot.onrender.com"
MINIAPP_URL = "https://gemad.onrender.com"

app = Flask(__name__)

application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("➡ /start ", update.effective_user.id)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open a Mini App", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )
    await update.message.reply_text(
        "Click the button to open a Mini App 🚀",
        reply_markup=keyboard
    )

application.add_handler(CommandHandler("start", start))

async def setup():

    await application.initialize()
    await application.start()

    info = await application.bot.get_webhook_info()
    if info.url != WEBHOOK_URL:
        await application.bot.delete_webhook()
        await application.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook: {WEBHOOK_URL}")
    else:
        print("🔁 Webhook")

# === Flask endpoint ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        print("📨 Update от Telegram:", data)
        update = Update.de_json(data, application.bot)
        asyncio.run(application.process_update(update))
        return "ok"
    return "Bot is working!"

if __name__ == "__main__":
    print("🚀 Bot starts...")
    asyncio.run(setup())
    print("✅Flask is running...")
    import time
    time.sleep(4)  
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))