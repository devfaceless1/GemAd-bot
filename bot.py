import os
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import Dispatcher, CommandHandler
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0)

# Команда /start
def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton(
            "Открыть Mini App",
            web_app=WebAppInfo(url="https://gemad.onrender.com/")
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Click the button to open mini-app:", reply_markup=reply_markup)

dispatcher.add_handler(CommandHandler("start", start))

# Роут для Webhook
@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# Установка webhook при старте
@app.before_first_request
def setup_webhook():
    bot.set_webhook(WEBHOOK_URL)

# Запуск Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
