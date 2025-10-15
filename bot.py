import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, WebAppInfo
from aiogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

# =======================
# Настройки
# =======================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 10))  # для теста можно 10 секунд

# =======================
# Инициализация
# =======================
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]
pending = db["pendingsubs"]
users = db["users"]

# =======================
# Функция одной итерации проверки очереди
# =======================
async def process_queue_iteration():
    now = datetime.utcnow()
    print(f"[{datetime.utcnow()}] 🔄 Проверка очереди подписок...")

    async for task in pending.find({"status": "waiting", "checkAfter": {"$lte": now}}):
        telegram_id = str(task["telegramId"])
        channel = task["channel"]  # должно быть @username или -100ID
        reward = task.get("reward", 15)

        print(f"[{datetime.utcnow()}] Проверяем: telegram_id={telegram_id}, channel={channel}, reward={reward}")

        # Проверяем, есть ли пользователь уже в subscribedChannels
        user_doc = await users.find_one({"telegramId": telegram_id})
        if user_doc and channel in user_doc.get("subscribedChannels", []):
            print(f"[{datetime.utcnow()}] Пользователь уже подписан, пропускаем")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})
            continue

        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=int(telegram_id))
            print(f"[{datetime.utcnow()}] Статус пользователя в канале {channel}: {member.status}")

            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await users.update_one(
                    {"telegramId": telegram_id},
                    {
                        "$inc": {"balance": reward, "totalEarned": reward},
                        "$addToSet": {"subscribedChannels": channel}
                    },
                    upsert=True
                )
                await bot.send_message(telegram_id, f"🎉 Ты был подписан и получил {reward}⭐!")
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded"}})
                print(f"[{datetime.utcnow()}] ✅ Reward начислен для {telegram_id}")
            else:
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})
                print(f"[{datetime.utcnow()}] ❌ Пользователь не подписан: {telegram_id}")

        except Exception as e:
            print(f"[{datetime.utcnow()}] ⚠️ Ошибка get_chat_member для {telegram_id} в {channel}: {e}")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed"}})

# =======================
# Фоновый цикл проверки очереди
# =======================
async def background_checker():
    while True:
        try:
            await process_queue_iteration()
        except Exception as e:
            print(f"[{datetime.utcnow()}] Ошибка в background_checker: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# =======================
# /start handler
# =======================
@dp.message(Command(commands=["start"]))
async def start_handler(message: types.Message):
    image_path = "images/gemad.jpg"
    photo = FSInputFile(image_path)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("Открыть мини-апп", web_app=WebAppInfo(url="https://gemad.onrender.com/"))]
        ]
    )

    await message.answer_photo(photo=photo, caption="Привет! Вот кнопка для мини-апп.", reply_markup=keyboard)

# =======================
# Webhook
# =======================
@app.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return PlainTextResponse("ok")

@app.get("/")
def root():
    return PlainTextResponse("Bot is running!")

# =======================
# Startup и Shutdown
# =======================
@app.on_event("startup")
async def on_startup():
    try:
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"⚠️ Не удалось установить вебхук: {e}")
    asyncio.create_task(background_checker())
    print("🚀 Фоновый чекер запущен...")

@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
    print("🛑 Bot session закрыт")
