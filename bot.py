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

# === /start handler ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("➡ /start ", update.effective_user.id)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open App", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )
    
    photo_path = "GemAd-logo.jpg"  
    await update.message.reply_photo(
        photo=open(photo_path, "rb"),
        caption="🎁 Welcome to GemAd! 🌟 Discover useful deals and earn gifts by subscribing! Launch the mini app and unlock rewards today! 🚀",
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
        print("📨 Update от Telegram:", data)
        update = Update.de_json(data, application.bot)
        asyncio.run(application.process_update(update))
        return "ok"
    return "Bot is working!"

# === Main ===
if __name__ == "__main__":
    print("🚀 Bot starts...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup())
    print("✅ Flask is running...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
