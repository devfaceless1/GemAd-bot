# bot.py — надёжный вариант с детальным логированием и резолвом channel -> chat_id
import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, WebAppInfo
from aiogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 10))  # seconds, reduce for testing

if not TOKEN or not MONGO_URI:
    raise SystemExit("ERROR: BOT_TOKEN and MONGO_URI must be set in environment or .env")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["test"]
pending = db["pendings"]
users = db["users"]

# -----------------------
# Helpers
# -----------------------
def now_str():
    return datetime.utcnow().isoformat()

async def safe_set_webhook(url: str, max_retries: int = 5):
    backoff = 1
    for attempt in range(1, max_retries + 1):
        try:
            await bot.set_webhook(url)
            print(f"[{now_str()}] ✅ Webhook установлен: {url}")
            return True
        except Exception as e:
            print(f"[{now_str()}] ⚠️ Попытка {attempt}/{max_retries} установить webhook не удалась: {e}")
            # если Telegram просит retry_after, выдержим паузу (если есть)
            if "retry after" in str(e).lower() or "too many requests" in str(e).lower() or "flood" in str(e).lower():
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            else:
                # для остальных ошибок даём небольшую паузу и пробуем ещё
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
    print(f"[{now_str()}] ❌ Не удалось установить webhook после {max_retries} попыток")
    return False

async def resolve_chat_id(raw_channel):
    if raw_channel is None:
        return None

    # если это уже число-строка или число
    try:
        if isinstance(raw_channel, int):
            return raw_channel
        chs = str(raw_channel).strip()
        # numeric channel id like -1001234567890
        if chs.lstrip("-").isdigit():
            return int(chs)
    except Exception:
        pass

    # Попробуем напрямую получить чат (works with @username or username)
    candidates = [str(raw_channel).strip()]
    if not str(raw_channel).startswith("@"):
        candidates.append("@" + str(raw_channel).strip())

    for cand in candidates:
        try:
            chat = await bot.get_chat(cand)
            print(f"[{now_str()}] ℹ️ get_chat('{cand}') -> id={chat.id}, type={chat.type}, title={getattr(chat,'title',None)}")
            return int(chat.id)
        except Exception as e:
            print(f"[{now_str()}] ⚠️ get_chat('{cand}') failed: {e}")

    print(f"[{now_str()}] ❌ Не удалось резолвить channel '{raw_channel}' в chat_id")
    return None

# -----------------------
# Основная логика проверки одной итерации
# -----------------------
async def process_queue_iteration():
    now = datetime.utcnow()
    print(f"[{now_str()}] 🔄 Начало итерации проверки очереди (now={now.isoformat()})")
    # Найдём задачи, у которых checkAfter <= now и статус waiting
    cursor = pending.find({"status": "waiting", "checkAfter": {"$lte": now}})
    async for task in cursor:
        tid = str(task.get("_id"))
        telegram_id_raw = task.get("telegramId")
        channel_raw = task.get("channel")
        reward = int(task.get("reward", 15))

        print(f"[{now_str()}] ▶ Task {tid}: telegramId={telegram_id_raw!r}, channel={channel_raw!r}, reward={reward}")

        # Приведём telegram id к int
        try:
            user_id = int(str(telegram_id_raw).strip())
        except Exception as e:
            print(f"[{now_str()}] ❌ Неверный telegramId в задаче {tid}: {telegram_id_raw!r} — помечаю failed ({e})")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": "invalid telegramId"}})
            continue

        # Резолвим channel -> chat_id
        chat_id = await resolve_chat_id(channel_raw)
        if chat_id is None:
            # если не резолвится — пометим failed (но можно менять на skipped, если нужно)
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": "channel_resolve_failed"}})
            print(f"[{now_str()}] ❌ Task {tid}: channel resolution failed, set status=failed")
            continue

        # Проверим, не было ли уже подписки зарегистрировано у пользователя
        try:
            user_doc = await users.find_one({"telegramId": str(user_id)})
            if user_doc:
                subs = user_doc.get("subscribedChannels", [])
                # сравниваем по chat_id строкой/числом — унифицируем хранение как строка chat_id
                if str(chat_id) in [str(s) for s in subs]:
                    print(f"[{now_str()}] ℹ️ Task {tid}: пользователь {user_id} уже в subscribedChannels -> пометил skipped")
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})
                    continue
        except Exception as e:
            print(f"[{now_str()}] ⚠️ Ошибка чтения users для task {tid}: {e}")

        # Попробуем получить статус участника
                # Попробуем получить статус участника
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            status = getattr(member, "status", None)
            status_str = str(status).lower() if status else None
            print(f"[{now_str()}] ℹ️ Task {tid}: get_chat_member(chat_id={chat_id}, user_id={user_id}) -> status={status_str}")
        except Exception as e:
            print(f"[{now_str()}] ⚠️ Ошибка get_chat_member для task {tid}, chat_id={chat_id}, user_id={user_id}: {e}")
            # запишем причину в задачу и пометим failed
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": f"get_chat_member_error: {str(e)}"}})
            continue

        # Если подписан — начисляем
        if status_str in ("member", "administrator", "creator", "owner"):
            try:
                res = await users.update_one(
                    {"telegramId": str(user_id)},
                    {
                        "$inc": {"balance": reward, "totalEarned": reward},
                        "$addToSet": {"subscribedChannels": str(chat_id)}
                    },
                    upsert=True
                )
                print(f"[{now_str()}] ✅ Task {tid}: Reward начислен (mongo modified={getattr(res,'modified_count',None)})")
                try:
                    await bot.send_message(user_id, f"🎉 Ты был подписан на канал и получил {reward}⭐!")
                    print(f"[{now_str()}] ℹ️ Уведомление отправлено пользователю {user_id}")
                except Exception as e_send:
                    print(f"[{now_str()}] ⚠️ Не удалось отправить уведомление пользователю {user_id}: {e_send}")
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "rewarded", "processedAt": datetime.utcnow()}})
            except Exception as e:
                print(f"[{now_str()}] ❌ Ошибка при обновлении users/pending для task {tid}: {e}")
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": f"mongo_update_error: {e}"}})
        else:
            # не подписан
            print(f"[{now_str()}] ❌ Task {tid}: пользователь {user_id} не является участником ({status_str}) — помечаю failed")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "memberStatus": str(status)}})

    print(f"[{now_str()}] ⏱ Итерация завершена")

# -----------------------
# Фоновый цикл
# -----------------------
async def background_checker():
    while True:
        try:
            await process_queue_iteration()
        except Exception as e:
            print(f"[{now_str()}] ❌ Фатальная ошибка в background_checker: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# -----------------------
# Handlers и Webhook
# -----------------------
@dp.message(Command(commands=["start"]))
async def start_handler(message: types.Message):
    image_path = "images/gemad.jpg"
    try:
        photo = FSInputFile(image_path)
    except Exception as e:
        print(f"[{now_str()}] ⚠️ Ошибка открытия изображения: {e}")
        photo = None

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть мини-апп", web_app=WebAppInfo(url="https://gemad.onrender.com/"))]
    ])
    if photo:
        await message.answer_photo(photo=photo, caption="Привет! Вот кнопка для мини-апп.", reply_markup=keyboard)
    else:
        await message.answer("Привет! (картинка не найдена)", reply_markup=keyboard)

@app.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return PlainTextResponse("ok")

@app.get("/")
def root():
    return PlainTextResponse("Bot is running!")

# -----------------------
# Startup / Shutdown
# -----------------------
@app.on_event("startup")
async def on_startup():
    if WEBHOOK_URL:
        await safe_set_webhook(WEBHOOK_URL)
    else:
        print(f"[{now_str()}] ⚠️ WEBHOOK_URL пустой — не ставлю webhook")

    asyncio.create_task(background_checker())
    print(f"[{now_str()}] 🚀 Background checker запущен (interval={CHECK_INTERVAL}s)")

@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.session.close()
        print(f"[{now_str()}] 🛑 Bot session закрыт")
    except Exception as e:
        print(f"[{now_str()}] ⚠️ Ошибка при закрытии bot.session: {e}")
