import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from dotenv import load_dotenv
import os

# =======================
# Настройки
# =======================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 10))

# =======================
# Инициализация
# =======================
bot = Bot(token=TOKEN)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]

# =======================
# Чекер подписок
# =======================
async def process_queue_iteration():
    now = datetime.utcnow()
    print(f"[{datetime.utcnow()}] 🔄 Проверка очереди подписок...")
    async for task in pending.find({"status": "waiting", "checkAfter": {"$lte": now}}):
        telegram_id = str(task["telegramId"])
        channel = task["channel"]
        reward = task.get("reward", 15)

        print(f"[{datetime.utcnow()}] Проверяем: telegram_id={telegram_id}, channel={channel}, reward={reward}")

        user_doc = await users.find_one({"telegramId": telegram_id})
        if user_doc and channel in user_doc.get("subscribedChannels", []):
            print(f"[{datetime.utcnow()}] Пользователь уже подписан, пропускаем")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})
            continue

        try:
            if not channel.startswith("@"):
                channel = f"@{channel}"

            member = await bot.get_chat_member(chat_id=channel, user_id=int(telegram_id))
            print(f"[{datetime.utcnow()}] Статус пользователя в канале: {member.status}")

            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                result = await users.update_one(
                    {"telegramId": telegram_id},
                    {
                        "$inc": {"balance": reward, "totalEarned": reward},
                        "$addToSet": {"subscribedChannels": channel}
                    },
                    upsert=True
                )
                print(f"[{datetime.utcnow()}] ✅ Reward начислен, modified_count={result.modified_count}")
                await bot.send_message(telegram_id, f"🎉 Ты был подписан и получил {reward}⭐!")
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded"}})
                print(f"[{datetime.utcnow()}] Статус задания обновлён: rewarded")
            else:
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
                print(f"[{datetime.utcnow()}] ❌ Пользователь не подписан, статус задания: failed")
        except Exception as e_inner:
            print(f"[{datetime.utcnow()}] Ошибка при проверке пользователя {telegram_id} на канале {channel}: {e_inner}")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})

async def background_checker():
    while True:
        try:
            await process_queue_iteration()
        except Exception as e:
            print(f"[{datetime.utcnow()}] Ошибка в background_checker: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# =======================
# Запуск
# =======================
async def main():
    print("🚀 Checker запущен...")
    await background_checker()

if __name__ == "__main__":
    asyncio.run(main())
