import os
import asyncio
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = f"https://gemad-bot.onrender.com"  # твой URL на Render

bot = Bot(token=TOKEN)
app = Flask(__name__)

# Создаем event loop для асинхронных операций
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Создаем и инициализируем Telegram приложение
application = Application.builder().token(TOKEN).build()
loop.run_until_complete(application.initialize())

# === Команды ===
async def start(update: Update, context):
    await update.message.reply_text("Привет! Бот успешно работает на Render 🚀")

async def echo(update: Update, context):
    await update.message.reply_text(update.message.text)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# === Flask Webhook ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, bot)
        loop.create_task(application.process_update(update))
        return "ok"
    return "Bot is running! ✅"

# === Устанавливаем webhook при запуске ===
async def set_webhook():
    await bot.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    print("✅ Устанавливаем webhook...")
    loop.run_until_complete(set_webhook())
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))