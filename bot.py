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

BROADCAST_FILE = "last_broadcast.json" # Файл для хранения ID отправленных сообщений

@dp.message()
async def broadcast(message: types.Message):
    # Проверяем, что пишет админ и есть ли кого рассылать
    if str(message.from_user.id) != str(ADMIN_ID) or not os.path.exists(USERS_FILE): 
        return
        
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
        
    sent_messages = [] # Сюда будем складывать данные для удаления
    
    for user_id in users:
        try:
            # Отправляем сообщение и сохраняем то, что вернул Телеграм
            msg_obj = await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
            
            # Сохраняем ID чата и ID сообщения
            sent_messages.append({
                "chat_id": user_id, 
                "message_id": msg_obj.message_id
            })
            await asyncio.sleep(0.05) # Пауза, чтобы Телеграм не забанил за спам
        except Exception: 
            pass # Если юзер заблокировал бота, просто пропускаем

    # Записываем историю этой рассылки в файл
    with open(BROADCAST_FILE, "w") as f:
        json.dump(sent_messages, f)
        
    await message.answer(f"✅ Рассылка завершена! Отправлено: {len(sent_messages)}.\n\nЕсли ошибся, отправь /delete_last чтобы всё удалить.")
from aiogram.exceptions import TelegramBadRequest # Добавь этот импорт в самый верх файла к остальным импортам

@dp.message(Command("delete_last"))
async def delete_last_broadcast(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): 
        return

    if not os.path.exists(BROADCAST_FILE):
        await message.answer("⚠ Нет данных о последней рассылке (возможно, она уже удалена).")
        return

    with open(BROADCAST_FILE, "r") as f:
        sent_messages = json.load(f)

    deleted_count = 0
    await message.answer("⏳ Начинаю удаление...")

    for item in sent_messages:
        try:
            await bot.delete_message(chat_id=item["chat_id"], message_id=item["message_id"])
            deleted_count += 1
            await asyncio.sleep(0.05)
        except TelegramBadRequest:
            # Ошибка возникает, если юзер уже сам удалил переписку или прошло слишком много времени
            pass 

    # Очищаем файл, чтобы не удалить лишнее в следующий раз
    os.remove(BROADCAST_FILE)
    await message.answer(f"🗑 Успешно удалено сообщений: {deleted_count} из {len(sent_messages)}.")
# --- ЛОГИКА ВЕБ-СЕРВЕРА (чтобы сайт открывался) ---
async def handle_index(request):
    return web.FileResponse('index.html')
# --- ДОБАВИТЬ СЮДА ---
async def save_progress(request):
    try:
        data = await request.json()
        # Сохраняем в файл results.json каждую новую попытку с новой строки
        with open("results.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

app = web.Application()
app.router.add_get('/', handle_index)
app.router.add_post('/save', save_progress) # <- Обязательно добавь этот маршрут
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
