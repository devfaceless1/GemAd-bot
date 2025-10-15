import os
import asyncio
from datetime import datetime
from aiogram import Bot, types
from aiogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from fastapi.responses import PlainTextResponse

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://gemad-bot.onrender.com")
CHECK_INTERVAL = 60  # сек

# Telegram bot
bot = Bot(token=TOKEN)

# MongoDB
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]

# FastAPI
app = FastAPI()


# === /start handler (optional, can add later) ===
async def send_start_message(chat_id: int):
    await bot.send_message(
        chat_id,
        "🎁 Welcome to GemAd! 🌟 Discover deals and earn rewards!"
    )


# === Checker ===
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
                        f"🎉 Ты был подписан и получил {reward}⭐!"
                    )
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded"}})
                else:
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
            except Exception as e:
                print(f"Ошибка проверки {telegram_id}: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# === Webhook endpoint ===
@app.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await bot.process_update(update)
    return PlainTextResponse("ok")


# === Startup tasks ===
@app.on_event("startup")
async def on_startup():
    # Устанавливаем webhook
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")

    # Запускаем чекер
    asyncio.create_task(process_queue())
    print("🚀 Checker запущен...")


# === Root endpoint ===
@app.get("/")
def root():
    return PlainTextResponse("Bot is running!")
