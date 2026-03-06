import os
import json
import asyncio
import time

from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = os.getenv("ADMIN_ID")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === ПУТИ К ФАЙЛАМ (С учетом Railway) ===
# Если есть несгораемый диск Railway (/data), используем его. Иначе сохраняем в текущую папку.
DATA_DIR = "/data" if os.path.exists("/data") else "."
USERS_FILE = f"{DATA_DIR}/users.json"
BROADCAST_FILE = f"{DATA_DIR}/last_broadcast.json"
RESULTS_FILE = f"{DATA_DIR}/results.json" # Сюда будут падать результаты из WebApp

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

# === БЛОК 1: КОМАНДЫ БОТА ===

@dp.message(Command("start"))
async def start(message: types.Message):
    save_user(message.from_user.id)
    # Сбрасываем кэш, чтобы у пользователей всегда открывалась свежая версия приложения
    safe_url = f"{WEBAPP_URL}?v={int(time.time())}"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Прокачать матан", web_app=WebAppInfo(url=safe_url))]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! 👋\nЖми кнопку ниже!", reply_markup=markup)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        await message.answer("🛠 Панель админа:\nОтправь любой текст/фото для массовой рассылки.\nОтправь /delete_last чтобы удалить последнюю рассылку.")

@dp.message(Command("delete_last"))
async def delete_last_broadcast(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): 
        return

    if not os.path.exists(BROADCAST_FILE):
        await message.answer("⚠ Нет данных о последней рассылке.")
        return

    try:
        with open(BROADCAST_FILE, "r") as f:
            sent_messages = json.load(f)
    except:
        await message.answer("⚠ Ошибка чтения файла рассылок.")
        return

    deleted_count = 0
    await message.answer("⏳ Начинаю удаление...")

    for item in sent_messages:
        try:
            await bot.delete_message(chat_id=item["chat_id"], message_id=item["message_id"])
            deleted_count += 1
            await asyncio.sleep(0.05)
        except TelegramBadRequest:
            # Игнорируем ошибку, если пользователь уже сам удалил сообщение
            pass 

    os.remove(BROADCAST_FILE)
    await message.answer(f"🗑 Успешно удалено сообщений: {deleted_count} из {len(sent_messages)}.")


# === БЛОК 2: РАССЫЛКА (Должна быть строго ПОСЛЕ всех команд!) ===

@dp.message()
async def broadcast(message: types.Message):
    # Если пишет не админ, или это команда (начинается с /) — игнорируем
    if str(message.from_user.id) != str(ADMIN_ID) or (message.text and message.text.startswith('/')): 
        return
        
    if not os.path.exists(USERS_FILE):
        await message.answer("⚠ Ошибка: База пользователей пуста. Никто еще не нажимал /start.")
        return

    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    except:
        await message.answer("⚠ Ошибка чтения базы пользователей.")
        return

    sent_messages = [] 
    
    for user_id in users:
        try:
            msg_obj = await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
            sent_messages.append({"chat_id": user_id, "message_id": msg_obj.message_id})
            await asyncio.sleep(0.05) 
        except Exception: 
            pass 

    with open(BROADCAST_FILE, "w") as f:
        json.dump(sent_messages, f)
        
    await message.answer(f"✅ Рассылка завершена! Отправлено: {len(sent_messages)} людям.\nДля отмены жми /delete_last")


# === БЛОК 3: ВЕБ-СЕРВЕР (Для работы мини-приложения) ===

async def handle_index(request):
    return web.FileResponse('index.html')

# Эта функция принимает результаты тестов от учеников и сохраняет их в файл
async def save_progress(request):
    try:
        data = await request.json()
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)
async def get_stats(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({"error": "No user_id"}, status=400)
    
    stats = {"total": 0, "correct": 0, "topics": {}}
    
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if str(data.get('user_id')) == str(user_id) or data.get('username') == request.query.get('username'):
                        stats["total"] += 1
                        if data.get('isCorrect'):
                            stats["correct"] += 1
                        
                        topic = data.get('topic', 'Общее')
                        if topic not in stats["topics"]:
                            stats["topics"][topic] = {"total": 0, "correct": 0}
                        stats["topics"][topic]["total"] += 1
                        if data.get('isCorrect'):
                            stats["topics"][topic]["correct"] += 1
                except: continue
                
    return web.json_response(stats)
app = web.Application()
app.router.add_get('/', handle_index)
app.router.add_post('/save', save_progress) # Маршрут для сохранения статистики


# === ЗАПУСК ===

async def main():
    asyncio.create_task(dp.start_polling(bot))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    print(f"Сервер запущен на порту {PORT}")
    await site.start()
    while True: 
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
