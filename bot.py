import os
import asyncio
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://gemad-bot.onrender.com"  # замени на свой Render URL

app = Flask(__name__)
bot = Bot(token=TOKEN)

# создаем event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# создаем и инициализируем приложение
application = Application.builder().token(TOKEN).build()

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Бот запущен и работает на Render 🚀")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# инициализация приложения
loop.run_until_complete(application.initialize())
loop.run_until_complete(application.start())  # <-- ключевая строчка!

# === Flask webhook ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, bot)
        loop.create_task(application.process_update(update))
        return "ok"
    return "Bot is running! ✅"

# === устанавливаем webhook при старте ===
async def set_webhook():
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.delete_webhook()
        await bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")

if __name__ == "__main__":
    print("🚀 Запуск бота...")
    loop.run_until_complete(set_webhook())
    print("✅ Всё готово. Flask сервер запущен.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))