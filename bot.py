# main.py
import os
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils.executor import start_polling
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["mybot_db"]

app = FastAPI()

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Привет! Бот работает!")

@app.post("/")
async def webhook(req: Request):
    data = await req.json()
    update = types.Update(**data)
    await dp.process_update(update)
    return {"ok": True}

async def checker():
    while True:
        # здесь проверка подписок и начисление наград
        await asyncio.sleep(60)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(checker())
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
