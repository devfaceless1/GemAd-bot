import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, WebAppInfo
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

# =======================
# Настройки
# =======================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com")

# =======================
# Инициализация
# =======================
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# =======================
# /start handler с картинкой и мини-апп
# =======================
@dp.message(Command(commands=["start"]))
async def start_handler(message: types.Message):
    image_path = "images/gemad.jpg"
    photo = FSInputFile(image_path)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть мини-апп",
                    web_app=WebAppInfo(url="https://gemad.onrender.com/")
                )
            ]
        ]
    )

    await message.answer_photo(
        photo=photo,
        caption="Привет! Вот кнопка для мини-апп.",
        reply_markup=keyboard
    )

# =======================
# Webhook
# =======================
@app.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
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
    # Ставим вебхук безопасно
    try:
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"⚠️ Не удалось установить вебхук: {e}")

# =======================
# Shutdown
# =======================
@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
    print("🛑 Bot session закрыт")
