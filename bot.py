import os
import asyncio
from flask import Flask, request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# === Настройки ===
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://gemad-bot.onrender.com"  # твой URL вебхука
MINIAPP_URL = "https://gemad.onrender.com"  # твой Mini App URL

app = Flask(__name__)
bot = Bot(token=TOKEN)

# Создаем Telegram Application
application = Application.builder().token(TOKEN).build()

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("➡ Получена команда /start от", update.effective_user.id)

    # Кнопка с Mini App
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть Mini App", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )
    await update.message.reply_text(
        "Привет! Нажми кнопку, чтобы открыть Mini App 🚀",
        reply_markup=keyboard
    )

application.add_handler(CommandHandler("start", start))

# === Устанавливаем webhook ===
async def set_webhook():
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.delete_webhook()
        await bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    else:
        print("🔁 Webhook уже установлен")

# === Flask endpoint ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        print("📨 Update от Telegram:", data)
        update = Update.de_json(data, bot)
        asyncio.run(process_update(update))
        return "ok"
    return "Бот работает ✅"

# === Асинхронная обработка апдейтов ===
async def process_update(update: Update):
    await application.initialize()
    await application.process_update(update)

# === Запуск ===
if __name__ == "__main__":
    print("🚀 Запуск бота...")
    asyncio.run(set_webhook())
    print("✅ Flask сервер запущен")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))