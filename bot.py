import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv


# === Инициализация FastAPI ===
app = FastAPI()

# === Загрузка переменных окружения ===
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://gemad-bot.onrender.com")
CHECK_INTERVAL = 60  # сек

# === Telegram bot ===
bot = Bot(token=TOKEN)
dp = Dispatcher()  # обязательно для aiogram 3.x

# === MongoDB ===
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]


# === Checker task ===
async def process_queue():
    """Проверяет очередь заданий и начисляет награды"""
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
                if member.status in [
                    ChatMemberStatus.MEMBER,
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.OWNER
                ]:
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


# === Простой обработчик команды /start ===
@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("🎁 Привет! Добро пожаловать в GemAd 🌟")


# === Webhook endpoint ===
@app.post("/")
async def telegram_webhook(request: Request):
    """Получение апдейтов от Telegram"""
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)  # ✅ правильный вызов для aiogram 3.x
    return PlainTextResponse("ok")


# === Startup tasks ===
@app.on_event("startup")
async def on_startup():
    """Устанавливает webhook и запускает checker"""
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")

    asyncio.create_task(process_queue())
    print("🚀 Checker запущен...")


# === Root endpoint (проверка состояния) ===
@app.get("/")
def root():
    return PlainTextResponse("Bot is running!")
