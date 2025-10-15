import os
import asyncio
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://gemad-bot.onrender.com"
MINIAPP_URL = "https://gemad.onrender.com"
MONGO_URI = os.getenv("MONGO_URI")

# === Flask ===
app = Flask(__name__)

# === Telegram Bot ===
application = Application.builder().token(TOKEN).build()

# === MongoDB ===
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]

CHECK_INTERVAL = 60

# === /start handler ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open App 🚀", web_app=WebAppInfo(url=MINIAPP_URL))]]
    )
    photo_path = "GemAd-logo.jpg"
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption="🎁 Welcome to GemAd! 🌟",
                reply_markup=keyboard,
            )
    else:
        await update.message.reply_text(
            "🎁 Welcome to GemAd! 🌟",
            reply_markup=keyboard,
        )

application.add_handler(CommandHandler("start", start))

# === Checker (подписки) ===
async def process_queue():
    while True:
        now = datetime.utcnow()
        async for task in pending.find({"status": "waiting", "checkAfter": {"$lte": now}}):
            telegram_id = int(task["telegramId"])
            channel = task["channel"]
            reward = task.get("reward", 15)
            user_doc = await users.find_one({"telegramId": str(telegram_id)})

            if user_doc and channel in user_doc.get("subscribedChannels", []):
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})
                continue

            try:
                member = await application.bot.get_chat_member(chat_id=channel, user_id=telegram_id)
                if member.status in ["member", "administrator", "owner"]:
                    await users.update_one(
                        {"telegramId": str(telegram_id)},
                        {"$inc": {"balance": reward, "totalEarned": reward},
                         "$addToSet": {"subscribedChannels": channel}},
                        upsert=True
                    )
                    await application.bot.send_message(
                        telegram_id,
                        f"🎉 Ты был подписан 5 минут и получил {reward}⭐!"
                    )
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded"}})
                else:
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
            except Exception as e:
                print(f"Ошибка проверки {telegram_id}: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# === Flask webhook endpoint ===
@app.route("/", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), main_loop)
        return "ok"
    return "Bot is working!"

# === Main ===
if __name__ == "__main__":
    print("🚀 Bot запускается...")

    main_loop = asyncio.get_event_loop()

    async def init():
        await application.initialize()
        await application.start()
        await application.bot.delete_webhook()
        await application.bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")

        # Запуск Checker параллельно
        main_loop.create_task(process_queue())

    main_loop.run_until_complete(init())
    print("✅ Flask сервер запущен...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
