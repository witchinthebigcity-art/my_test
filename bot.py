import os
import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# Берем настройки из переменных Railway
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Файл для хранения ID пользователей (чтобы знать, кому слать рекламу)
USERS_FILE = "users.json"

def save_user(user_id):
    users = set()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = set(json.load(f))
    users.add(user_id)
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

@dp.message(Command("start"))
async def start(message: types.Message):
    save_user(message.from_user.id)
    
    # Кнопка для открытия твоего приложения
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Прокачать матан", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я твой личный тренажер по математике. Нажимай кнопку ниже, чтобы начать прокачку!",
        reply_markup=markup
    )

# Команда для админа, чтобы запустить рассылку
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        await message.answer("Отправь сообщение (текст или фото с текстом), и я разошлю его всем ученикам!")
    else:
        await message.answer("У тебя нет прав доступа к этой команде. 😉")

# Логика самой рассылки
@dp.message()
async def broadcast(message: types.Message):
    # Проверяем, что пишет именно админ
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    if not os.path.exists(USERS_FILE):
        await message.answer("Пользователей пока нет.")
        return

    with open(USERS_FILE, "r") as f:
        users = json.load(f)

    count = 0
    for user_id in users:
        try:
            await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
            count += 1
            await asyncio.sleep(0.05) # Защита от спам-фильтра Телеграма
        except Exception:
            pass

    await message.answer(f"✅ Рассылка завершена!\nПолучили: {count} чел.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
