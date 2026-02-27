import asyncio
import json
import os
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

# Получаем переменные окружения (Railway задаст их автоматически)
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL") # Сюда впишем домен, который даст Railway
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID", "-1003677230845")
PORT = int(os.getenv("PORT", 8080)) # Railway сам назначает порт

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Временная память для имен (при перезагрузке сервера будет сбрасываться, 
# в идеале потом подключим SQLite)
user_data_db = {}

# --- ЛОГИКА БОТА ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    # Кнопка для запуска Web App
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Прокачать матан 🚀", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True
    )
    # Если имя не знаем, можно спросить, но для простоты сразу даем кнопку
    await message.answer(
        "Привет! Готов прокачать свои знания? Нажимай на кнопку ниже и выбирай свой класс!", 
        reply_markup=kb
    )

@dp.message(F.web_app_data)
async def web_app_data_handler(message: Message):
    data = json.loads(message.web_app_data.data)
    action = data.get('action')
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    if action == 'report_error':
        error_context = data.get('context')
        grade = data.get('class')
        text = f"⚠️ Ошибка от {username}\nКласс: {grade}\nКонтекст: {error_context}"
        await bot.send_message(chat_id=ADMIN_GROUP_ID, message_thread_id=1, text=text)

    elif action == 'support_request':
        text = f"✉️ {username} запрашивает поддержку. Напишите ему в личные сообщения!"
        await bot.send_message(chat_id=ADMIN_GROUP_ID, message_thread_id=1, text=text)

    elif action == 'save_result':
        grade = data.get('class')
        topic = data.get('topic')
        is_correct = data.get('isCorrect')
        result_text = "Верно" if is_correct else "Ошибка"
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Здесь будет логика записи в Google Таблицу через gspread
        # gc = gspread.service_account(filename='credentials.json')
        # sh = gc.open_by_url("ТВОЯ_ССЫЛКА_НА_ПРИВАТНУЮ_ТАБЛИЦУ")
        # worksheet = sh.sheet1
        # worksheet.append_row([date_str, username, grade, topic, result_text])
        
        print(f"Результат сохранен: {username}, Класс: {grade}, Тема: {topic}, Итог: {result_text}")

# --- ЛОГИКА ВЕБ-СЕРВЕРА ---
async def handle_index(request):
    # Отдаем наш HTML файл, когда Telegram запрашивает WEBAPP_URL
    return web.FileResponse('index.html')

async def main():
    # Настраиваем aiohttp сервер
    app = web.Application()
    app.router.add_get('/', handle_index)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    print(f"Сервер запущен на порту {PORT}")
    
    # Запускаем бота параллельно с сервером
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
