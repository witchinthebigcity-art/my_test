import os
import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# Настройки из Railway
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = os.getenv("ADMIN_ID")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=TOKEN)
dp = Dispatcher()
USERS_FILE = "users.json"

# --- ЛОГИКА БОТА ---
def save_user(user_id):
    users = set()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                users = set(json.load(f))
        except: pass
    users.add(user_id)
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

import time # Добавь в начало файла, где импорты

@dp.message(Command("start"))
async def start(message: types.Message):
    save_user(message.from_user.id)
    
    # Добавляем параметр времени (cache-buster), чтобы убить кэш ТГ
    cache_buster = int(time.time())
    safe_url = f"{WEBAPP_URL}?v={cache_buster}"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Прокачать матан", web_app=WebAppInfo(url=safe_url))]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! 👋\nЖми кнопку ниже!", reply_markup=markup)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        await message.answer("🛠 Панель админа: отправь любое сообщение для рассылки!")

@dp.message()
async def broadcast(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID) or not os.path.exists(USERS_FILE): return
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    for user_id in users:
        try:
            await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
            await asyncio.sleep(0.05)
        except: pass
    await message.answer("✅ Рассылка завершена!")

# --- ЛОГИКА ВЕБ-СЕРВЕРА (чтобы сайт открывался) ---
async def handle_index(request):
    return web.FileResponse('index.html')

app = web.Application()
app.router.add_get('/', handle_index)

# Запуск всего вместе
async def main():
    # Запускаем бота в фоне
    asyncio.create_task(dp.start_polling(bot))
    # Запускаем веб-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    print(f"Сервер запущен на порту {PORT}")
    await site.start()
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
