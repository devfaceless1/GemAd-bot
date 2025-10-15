import asyncio
from datetime import datetime
from flask import Flask
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

bot = Bot(token=TOKEN)
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]

CHECK_INTERVAL = 60  # интервал проверки

app = Flask(__name__)

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
                member = await bot.get_chat_member(chat_id=channel, user_id=telegram_id)
                if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    await users.update_one(
                        {"telegramId": str(telegram_id)},
                        {
                            "$inc": {"balance": reward, "totalEarned": reward},
                            "$addToSet": {"subscribedChannels": channel}
                        },
                        upsert=True
                    )
                    await bot.send_message(
                        telegram_id,
                        f"🎉 Ты подписан на канал и получил {reward}⭐!"
                    )
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded"}})
                else:
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
            except Exception as e:
                print(f"Ошибка проверки {telegram_id}: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# Запускаем чекер параллельно с Flask
@app.before_first_request
def start_checker():
    loop = asyncio.get_event_loop()
    loop.create_task(process_queue())

@app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
