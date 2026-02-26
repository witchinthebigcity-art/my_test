import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- НАСТРОЙКИ ---
TOKEN = "8510677565:AAFkWjGuF2f7PiTj_zHV_RqInrT3D9wTrYw"
# Твой домен на Railway
WEBAPP_URL = "https://mytest-production-5084.up.railway.app"

# 1. ЛОГИКА ВЕБ-СЕРВЕРА (отдача Mini App)
async def handle_index(request):
    """Отдает файл index.html при переходе по ссылке"""
    try:
        # Пытаемся открыть файл index.html в той же папке
        with open("index.html", "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="Файл index.html не найден на сервере!", status=404)

# 2. ЛОГИКА TELEGRAM БОТА
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Постоянная кнопка под строкой ввода
main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🎓 Выбрать класс")]], 
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    """Приветствие при команде /start"""
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать обучение", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Добро пожаловать в Math Universe. Твоя лаборатория знаний готова.",
        reply_markup=main_kb
    )
    await message.answer("Нажми на кнопку ниже, чтобы войти:", reply_markup=inline_kb)

@dp.message(lambda m: m.text == "🎓 Выбрать класс")
async def open_app_via_menu(message: types.Message):
    """Открытие приложения через кнопку меню"""
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть Math Universe 🚀", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer("Твоя база знаний ждет тебя:", reply_markup=inline_kb)

# 3. ЗАПУСК ОБОИХ СЕРВИСОВ
async def main():
    # Настройка веб-приложения
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    
    # Для Railway важно брать порт из переменных окружения
    port = int(os.getenv("PORT", 8080))
    
    # Запуск веб-сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    logging.info(f"--- ВЕБ-СЕРВЕР ЗАПУЩЕН НА ПОРТУ {port} ---")
    await site.start()

    # Запуск бота (Polling)
    logging.info("--- БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("--- СЕРВЕР ОСТАНОВЛЕН ---")
