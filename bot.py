import os
import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# Настройки из Railway
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Файл для базы данных учеников
USERS_FILE = "users.json"

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

@dp.message(Command("start"))
async def start(message: types.Message):
    save_user(message.from_user.id)
    
    # Главная кнопка входа в приложение
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Прокачать матан", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я твой личный тренажер. Жми кнопку ниже, чтобы начать решать задачи!",
        reply_markup=markup
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    # Проверка: тот ли это ID, который мы вписали в Railway
    if str(message.from_user.id) == str(ADMIN_ID):
        await message.answer("🛠 **Панель админа**\n\nОтправь любое сообщение (текст, фото, пост), и я разошлю его всем твоим ученикам!")
    else:
        await message.answer("Сорри, эта команда только для СуперТьютора. 😉")

@dp.message()
async def broadcast(message: types.Message):
    # Рассылка срабатывает, только если пишет админ
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    if not os.path.exists(USERS_FILE):
        await message.answer("В базе пока 0 учеников.")
        return

    with open(USERS_FILE, "r") as f:
        users = json.load(f)

    count = 0
    for user_id in users:
        try:
            # Копируем сообщение в оригинальном виде (с фото и кнопками)
            await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
            count += 1
            await asyncio.sleep(0.05) # Пауза, чтобы Телеграм не забанил за спам
        except:
            pass

    await message.answer(f"📢 **Рассылка завершена!**\nСообщение получили: {count} чел.")

async def main():
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
