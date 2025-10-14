import asyncio
from datetime import datetime
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

CHECK_INTERVAL = 60  # секунд между проверками очереди

async def process_queue():
    while True:
        now = datetime.utcnow()
        print(f"⏱ Проверка очереди: {now.isoformat()}")
        async for task in pending.find({"status": "waiting", "checkAfter": {"$lte": now}}):
            telegram_id = int(task["telegramId"])
            channel = task["channel"]
            reward = task.get("reward", 15)

            print(f"🔹 Проверяем задачу: user={telegram_id}, channel={channel}, reward={reward}")

            # Проверяем, не начисляли ли уже пользователю за этот канал
            user_doc = await users.find_one({"telegramId": str(telegram_id)})
            if user_doc and channel in user_doc.get("subscribedChannels", []):
                print(f"⚠ Пользователь {telegram_id} уже подписан на {channel}, пропускаем")
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})
                continue

            try:
                member = await bot.get_chat_member(chat_id=channel, user_id=telegram_id)
                if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    # Начисляем звёзды
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
                        f"🎉 Ты был подписан 5 минут и получил {reward}⭐!"
                    )
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded"}})
                    print(f"✅ Начислены {reward}⭐ пользователю {telegram_id} за {channel}")
                else:
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
                    print(f"❌ Пользователь {telegram_id} не подписан на {channel}, отметка failed")
            except Exception as e:
                print(f"⚠ Ошибка проверки {telegram_id} на канале {channel}: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print("🚀 Checker запущен...")
    loop = asyncio.get_event_loop()
    loop.create_task(process_queue())
    loop.run_forever()
