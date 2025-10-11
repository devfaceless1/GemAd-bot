import os
import asyncio
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

# Загружаем .env локально
load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Flask приложение
app = Flask(__name__)

# Telegram приложение
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

# Регистрируем обработчик команды
application.add_handler(CommandHandler("start", start))

# Роут для Webhook
@app.post("/")
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "ok"

# Основной запуск
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    async def main():
        # Устанавливаем webhook перед запуском Flask
        await application.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
        await app.run_task(host="0.0.0.0", port=port)

    asyncio.run(main())