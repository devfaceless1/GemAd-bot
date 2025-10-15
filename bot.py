import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
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
CHECK_INTERVAL = 60  # секунд

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
# Checker (асинхронный)
# =======================
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

# =======================
# Хэндлер /start
# =======================
@dp.message(Command(commands=["start"]))
async def start_handler(message: types.Message):
    # Картинка
    photo = InputFile("start_image.jpg")  # замените на путь к вашей картинке
    # Кнопка на мини-апп
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть мини-апп", url="https://your-mini-app.com")]
    ])
    # Отправка
    await message.answer_photo(photo=photo, caption="Привет! Вот описание и кнопка для мини-апп.", reply_markup=keyboard)

# =======================
# Webhook
# =======================
@app.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(update)  # Aiogram v3 корректно обрабатывает обновления
    return PlainTextResponse("ok")

# =======================
# Root endpoint
# =======================
@app.get("/")
def root():
    return PlainTextResponse("Bot is running!")

# =======================
# Startup
# =======================
@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    asyncio.create_task(process_queue())
    print("🚀 Checker запущен...")

# =======================
# Пример хэндлера сообщений (echo для всех остальных)
# =======================
@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Echo: {message.text}")
