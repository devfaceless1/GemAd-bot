import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://gemad-bot.onrender.com"
MINIAPP_URL = "https://gemad.onrender.com"

app = Flask(__name__)

# Создаем Application сразу
application = Application.builder().token(TOKEN).build()

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("➡ Получена команда /start от", update.effective_user.id)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть Mini App", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )
    await update.message.reply_text(
        "Привет! Нажми кнопку, чтобы открыть Mini App 🚀",
        reply_markup=keyboard
    )

application.add_handler(CommandHandler("start", start))

# === Инициализация и webhook ===
async def setup():
    # Инициализация Application (вместе с ботом)
    await application.initialize()
    await application.start()
    # Установка webhook
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
        # Асинхронная обработка
        asyncio.run(application.process_update(update))
        return "ok"
    return "Бот работает ✅"

# === Запуск Flask и setup ===
if __name__ == "__main__":
    print("🚀 Запуск бота...")
    asyncio.run(setup())
    print("✅ Flask сервер запущен, ожидание входящих сообщений...")
    import time
    time.sleep(4)  # 👈 Telegram успевает получить webhook перед первым апдейтом
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))