# bot.py — stable version with detailed logging and proper channel -> chat_id resolution
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
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 10))  # seconds

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
            print(f"[{now_str()}] ✅ Webhook set successfully: {url}")
            return True
        except Exception as e:
            print(f"[{now_str()}] ⚠️ Attempt {attempt}/{max_retries} to set webhook failed: {e}")
            if "retry after" in str(e).lower() or "too many requests" in str(e).lower() or "flood" in str(e).lower():
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            else:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
    print(f"[{now_str()}] ❌ Failed to set webhook after {max_retries} attempts")
    return False

async def resolve_chat_id(raw_channel):
    if raw_channel is None:
        return None
    try:
        if isinstance(raw_channel, int):
            return raw_channel
        chs = str(raw_channel).strip()
        if chs.lstrip("-").isdigit():
            return int(chs)
    except Exception:
        pass

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

    print(f"[{now_str()}] ❌ Could not resolve channel '{raw_channel}' to chat_id")
    return None

# -----------------------
# Main queue processing logic
# -----------------------
async def process_queue_iteration():
    now = datetime.utcnow()
    print(f"[{now_str()}] 🔄 Queue iteration started (now={now.isoformat()})")

    cursor = pending.find({"status": "waiting", "checkAfter": {"$lte": now}})
    async for task in cursor:
        tid = str(task.get("_id"))
        telegram_id_raw = task.get("telegramId")
        channel_raw = task.get("channel")
        reward = int(task.get("reward", 15))

        print(f"[{now_str()}] ▶ Task {tid}: telegramId={telegram_id_raw!r}, channel={channel_raw!r}, reward={reward}")

        try:
            user_id = int(str(telegram_id_raw).strip())
        except Exception as e:
            print(f"[{now_str()}] ❌ Invalid telegramId in task {tid}: {telegram_id_raw!r} — marked as failed ({e})")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": "invalid telegramId"}})
            continue

        chat_id = await resolve_chat_id(channel_raw)
        if chat_id is None:
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": "channel_resolve_failed"}})
            print(f"[{now_str()}] ❌ Task {tid}: channel resolution failed, marked failed")
            continue

        try:
            user_doc = await users.find_one({"telegramId": str(user_id)})
            if user_doc:
                subs = user_doc.get("subscribedChannels", [])
                if str(chat_id) in [str(s) for s in subs]:
                    print(f"[{now_str()}] ℹ️ Task {tid}: user {user_id} already subscribed -> skipped")
                    await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})
                    continue
        except Exception as e:
            print(f"[{now_str()}] ⚠️ Error reading users for task {tid}: {e}")

        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            status_enum = getattr(member, "status", None)
            status_str = status_enum.value.lower() if status_enum else None
            print(f"[{now_str()}] ℹ️ Task {tid}: get_chat_member(chat_id={chat_id}, user_id={user_id}) -> status={status_str}")
        except Exception as e:
            print(f"[{now_str()}] ⚠️ Error get_chat_member for task {tid}, chat_id={chat_id}, user_id={user_id}: {e}")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": f"get_chat_member_error: {str(e)}"}})
            continue

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
                print(f"[{now_str()}] ✅ Task {tid}: reward granted (mongo modified={getattr(res,'modified_count',None)})")
                try:
                    await bot.send_message(user_id, f"🎉 You were subscribed and earned {reward}⭐!")
                    print(f"[{now_str()}] ℹ️ Notification sent to user {user_id}")
                except Exception as e_send:
                    print(f"[{now_str()}] ⚠️ Failed to notify user {user_id}: {e_send}")

                # ✅ Remove rewarded task from DB
                await pending.delete_one({"_id": task["_id"]})
                print(f"[{now_str()}] 🗑️ Task {tid} removed from DB (rewarded)")

            except Exception as e:
                print(f"[{now_str()}] ❌ Error updating users/pending for task {tid}: {e}")
                await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "error": f"mongo_update_error: {e}"}})
        else:
            print(f"[{now_str()}] ❌ Task {tid}: user {user_id} not a member ({status_str}) — marked failed")
            await pending.update_one({"_id": task["_id"]}, {"$set": {"status": "failed", "memberStatus": str(status_enum)}})

    print(f"[{now_str()}] ⏱ Queue iteration finished")

# -----------------------
# Background loop
# -----------------------
async def background_checker():
    while True:
        try:
            await process_queue_iteration()
        except Exception as e:
            print(f"[{now_str()}] ❌ Fatal error in background_checker: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# -----------------------
# Handlers and Webhook
# -----------------------
@dp.message(Command(commands=["start"]))
async def start_handler(message: types.Message):
    image_path = "images/gemad.jpg"
    try:
        photo = FSInputFile(image_path)
    except Exception as e:
        print(f"[{now_str()}] ⚠️ Failed to open image: {e}")
        photo = None

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Open Mini App", web_app=WebAppInfo(url="https://gemad.onrender.com/"))]
    ])
    if photo:
        await message.answer_photo(photo=photo, caption="Hello! Tap to open the mini app.", reply_markup=keyboard)
    else:
        await message.answer("Hello! (image not found)", reply_markup=keyboard)

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
    asyncio.create_task(background_checker())
    print(f"[{now_str()}] 🚀 Background checker started (interval={CHECK_INTERVAL}s)")

@app.on_event("shutdown")
async def on_shutdown():
    print(f"[{now_str()}] ⚠️ FastAPI shutdown — background tasks may be cut off")
