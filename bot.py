import os
import asyncio
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Flask приложение
app = Flask(__name__)

# Telegram Application
application = Application.builder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton(
            "Открыть Mini App",
            web_app=WebAppInfo(url="https://your-mini-app.com")
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Нажми кнопку, чтобы открыть мини-приложение:",
        reply_markup=reply_markup
    )

# Регистрируем обработчик
application.add_handler(CommandHandler("start", start))

# Webhook endpoint
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    # используем уже готовый event loop Flask
    asyncio.create_task(application.process_update(update))
    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    async def main():
        # 1️⃣ Инициализация Telegram Application
        await application.initialize()
        # 2️⃣ Устанавливаем webhook
        await application.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
        # 3️⃣ Запускаем Flask (синхронно)
        app.run(host="0.0.0.0", port=port)

    asyncio.run(main())