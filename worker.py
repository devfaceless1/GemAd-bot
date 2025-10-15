import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Инициализация бота и базы данных
bot = Bot(token=TOKEN)
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]

CHECK_INTERVAL = 60  # интервал проверки в секундах

async def process_queue():
    print("🚀 Checker запущен...")
    while True:
        now = datetime.utcnow()

        # Находим все заявки со статусом "waiting" и checkAfter ≤ текущее время
        async for task in pending.find({"status": "waiting", "checkAfter": {"$lte": now}}):
            telegram_id = int(task["telegramId"])
            channel = task["channel"]
            reward = task.get("reward", 15)

            # Проверяем, есть ли пользователь в базе и подписан ли на канал
            user_doc = await users.find_one({"telegramId": str(telegram_id)})
            if user_doc and channel in user_doc.get("subscribedChannels", []):
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})
                continue

            try:
                member = await bot.get_chat_member(chat_id=channel, user_id=telegram_id)
                if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    # Начисляем награду
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
                    print(f"✅ Пользователь {telegram_id} награждён за {channel}")
                else:
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
                    print(f"❌ Пользователь {telegram_id} не подписан на {channel}")
            except Exception as e:
                print(f"Ошибка проверки {telegram_id}: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(process_queue())
    except KeyboardInterrupt:
        print("Checker остановлен вручную")
