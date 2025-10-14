import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

bot = Bot(token=TOKEN)
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]

async def process_queue():
    while True:
        now = datetime.utcnow()
        async for task in pending.find({"status": "waiting", "checkAfter": {"$lte": now}}):
            telegram_id = int(task["telegramId"])
            channel = task["channel"]
            try:
                member = await bot.get_chat_member(chat_id=channel, user_id=telegram_id)
                if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    reward = 15
                    await users.update_one(
                        {"telegramId": str(telegram_id)},
                        {"$inc": {"balance": reward, "totalEarned": reward},
                         "$addToSet": {"subscribedChannels": channel}}
                    )
                    await bot.send_message(telegram_id, f"🎉 Ты был подписан 12 часов и получил {reward}⭐ звёзд!")
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded"}})
                else:
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
            except Exception as e:
                print(f"Ошибка проверки {telegram_id}: {e}")
        await asyncio.sleep(600)  

asyncio.run(process_queue())
