import os
import json
import asyncio
import ssl
import time

import aiohttp
import certifi
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

from community import CommunityError, CommunityStore, validate_telegram_init_data
from questions import QuestionFormatError, SUPPORTED_GRADES, parse_questions_csv

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = os.getenv("ADMIN_ID")
PORT = int(os.getenv("PORT", 8080))
QUESTIONS_CSV_URL = os.getenv(
    "QUESTIONS_CSV_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyYBIArwn-npZYPgPwIazi4HzVR4DzusAc1VvJ_eQklHkYBElS7r0pwZzx-Pe2tPnoop9sFBpFMZWj/pub?output=csv",
)
QUESTIONS_CACHE_TTL = int(os.getenv("QUESTIONS_CACHE_TTL", "60"))
LOCAL_IMAGE_QUESTIONS_FILE = os.getenv("LOCAL_IMAGE_QUESTIONS_FILE", "image_questions.csv")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === ПУТИ К ФАЙЛАМ (С учетом Railway) ===
# Если есть несгораемый диск Railway (/data), используем его. Иначе сохраняем в текущую папку.
DATA_DIR = "/data" if os.path.exists("/data") else "."
USERS_FILE = f"{DATA_DIR}/users.json"
BROADCAST_FILE = f"{DATA_DIR}/last_broadcast.json"
RESULTS_FILE = f"{DATA_DIR}/results.json" # Сюда будут падать результаты из WebApp
COMMUNITY_FILE = f"{DATA_DIR}/community.json"

community_store = CommunityStore(COMMUNITY_FILE)

questions_cache = {"loaded_at": 0.0, "items": []}
questions_cache_lock = asyncio.Lock()

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


def load_user_ids(path=None):
    source_path = path or USERS_FILE
    if not os.path.exists(source_path):
        return []
    with open(source_path, "r", encoding="utf-8") as source:
        payload = json.load(source)
    values = payload.keys() if isinstance(payload, dict) else payload
    result = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return list(dict.fromkeys(result))


async def send_broadcast(source_message=None, text=None, user_ids=None, bot_client=None, delay=0.06):
    """Copy one Telegram message (including media) or send text to all known users."""
    bot_client = bot_client or bot
    user_ids = list(user_ids if user_ids is not None else load_user_ids())
    report = {"sent": [], "blocked": 0, "failed": 0, "total": len(user_ids)}

    for user_id in user_ids:
        for attempt in range(2):
            try:
                if source_message is not None:
                    sent = await bot_client.copy_message(
                        chat_id=user_id,
                        from_chat_id=source_message.chat.id,
                        message_id=source_message.message_id,
                    )
                else:
                    sent = await bot_client.send_message(chat_id=user_id, text=text)
                report["sent"].append({"chat_id": user_id, "message_id": sent.message_id})
                break
            except TelegramRetryAfter as error:
                if attempt == 0:
                    await asyncio.sleep(float(error.retry_after) + 0.2)
                    continue
                report["failed"] += 1
            except TelegramForbiddenError:
                report["blocked"] += 1
                break
            except (TelegramBadRequest, TelegramNetworkError, TelegramServerError):
                report["failed"] += 1
                break
            except Exception:
                report["failed"] += 1
                break
        if delay:
            await asyncio.sleep(delay)
    return report

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
        await message.answer(
            "🛠 Панель администратора\n\n"
            "1. Отправьте боту готовое сообщение: текст, фото, видео, аудио или голосовое.\n"
            "2. Ответьте на это сообщение командой /sendall или /all.\n\n"
            "Также можно отправить: /sendall текст сообщения\n"
            "/users — количество и список пользователей\n"
            "/delete_last — удалить последнюю рассылку у получателей"
        )


@dp.message(Command("sendall", "all"))
async def broadcast_command(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("Эта команда доступна только администратору.")
        return

    source_message = message.reply_to_message
    command_parts = (message.text or "").split(maxsplit=1)
    direct_text = command_parts[1].strip() if len(command_parts) > 1 else ""
    if source_message is None and not direct_text:
        await message.answer(
            "Сначала отправьте текст, фото, видео, аудио или голосовое, "
            "а затем ответьте на него командой /sendall."
        )
        return

    try:
        users = load_user_ids()
    except (OSError, json.JSONDecodeError):
        await message.answer("⚠ Не удалось прочитать базу пользователей.")
        return
    if not users:
        await message.answer("⚠ База пользователей пуста. Пока никто не нажал /start.")
        return

    status = await message.answer(f"⏳ Начинаю рассылку для {len(users)} пользователей…")
    report = await send_broadcast(
        source_message=source_message,
        text=direct_text or None,
        user_ids=users,
    )
    with open(BROADCAST_FILE, "w", encoding="utf-8") as target:
        json.dump(report["sent"], target, ensure_ascii=False)

    await status.edit_text(
        "✅ Рассылка завершена\n"
        f"Доставлено: {len(report['sent'])}\n"
        f"Бот заблокирован: {report['blocked']}\n"
        f"Другие ошибки: {report['failed']}\n\n"
        "Удалить доставленные сообщения: /delete_last"
    )

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
@dp.message(Command("users"))
async def get_all_users(message: types.Message):
    # Проверка, что пишет именно админ
    if str(message.from_user.id) != str(ADMIN_ID): 
        return

    if not os.path.exists(USERS_FILE):
        await message.answer("⚠ База пользователей пока пуста.")
        return

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        await message.answer("⚠ Ошибка чтения файла.")
        return

    # Создаем временный файл-отчет
    report_path = f"{DATA_DIR}/users_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"📊 Всего в боте: {len(users)} чел.\n")
        f.write("="*40 + "\n\n")
        
        # Если база уже в новом формате (словарь)
        if isinstance(users, dict):
            for uid, info in users.items():
                name = info.get("name", "Без имени")
                username = f"@{info.get('username')}" if info.get('username') else "Нет @username"
                f.write(f"ID: {uid} | Имя: {name} | ТГ: {username}\n")
        # Если база еще старая (список ID)
        else:
            for uid in users:
                f.write(f"ID: {uid} (Нужно обновить данные, нажав /start)\n")

    # Отправляем файл пользователю
    doc = FSInputFile(report_path)
    await message.answer_document(doc, caption="👥 База твоих учеников")

# === БЛОК 3: ВЕБ-СЕРВЕР (Для работы мини-приложения) ===

async def handle_index(request):
    return web.FileResponse('index.html')


async def handle_styles(request):
    return web.FileResponse('app.css')


async def handle_community_script(request):
    return web.FileResponse('community.js')


async def handle_math_script(request):
    return web.FileResponse('math-format.js')


def _authenticated_user(request):
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return validate_telegram_init_data(init_data, TOKEN)


def _community_error(error, status=400):
    return web.json_response({"error": str(error)}, status=status)


async def _load_questions():
    now = time.monotonic()
    if questions_cache["items"] and now - questions_cache["loaded_at"] < QUESTIONS_CACHE_TTL:
        return questions_cache["items"]

    async with questions_cache_lock:
        now = time.monotonic()
        if questions_cache["items"] and now - questions_cache["loaded_at"] < QUESTIONS_CACHE_TTL:
            return questions_cache["items"]

        separator = "&" if "?" in QUESTIONS_CSV_URL else "?"
        cache_busted_url = f"{QUESTIONS_CSV_URL}{separator}t={int(time.time())}"
        timeout = aiohttp.ClientTimeout(total=15)
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(cache_busted_url) as response:
                response.raise_for_status()
                csv_text = await response.text()

        questions = parse_questions_csv(csv_text)
        if os.path.exists(LOCAL_IMAGE_QUESTIONS_FILE):
            with open(LOCAL_IMAGE_QUESTIONS_FILE, "r", encoding="utf-8") as source:
                questions.extend(parse_questions_csv(source.read()))
        questions = list({question.question_id: question for question in questions}.values())
        questions_cache["items"] = questions
        questions_cache["loaded_at"] = time.monotonic()
        return questions


async def get_questions(request):
    try:
        grade = int(request.query.get("grade", ""))
    except ValueError:
        return web.json_response({"error": "Укажите класс от 8 до 11"}, status=400)

    if grade not in SUPPORTED_GRADES:
        return web.json_response({"error": "Поддерживаются только 8–11 классы"}, status=400)

    try:
        questions = await _load_questions()
    except QuestionFormatError as error:
        return web.json_response({"error": str(error)}, status=502)
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        print(f"Ошибка загрузки Google Таблицы: {error}")
        return web.json_response(
            {"error": "Не удалось загрузить Google Таблицу. Проверьте публикацию и ссылку."},
            status=502,
        )

    grade_questions = [question.as_dict() for question in questions if question.grade == grade]
    return web.json_response(
        {"grade": grade, "count": len(grade_questions), "questions": grade_questions},
        headers={"Cache-Control": "no-store"},
    )

# Эта функция принимает результаты тестов от учеников и сохраняет их в файл
async def save_progress(request):
    try:
        data = await request.json()
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        if init_data:
            user = validate_telegram_init_data(init_data, TOKEN)
            await community_store.record_attempt(user, data)
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        return web.json_response({"status": "success"})
    except CommunityError as error:
        return _community_error(error, status=401)
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def get_profile(request):
    try:
        return web.json_response(await community_store.get_profile(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=401)


async def update_profile(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        return web.json_response(await community_store.update_profile(user, payload))
    except CommunityError as error:
        return _community_error(error, status=422)


async def get_avatar(request):
    avatar_path = community_store.avatar_path(request.match_info.get("filename"))
    if not avatar_path:
        raise web.HTTPNotFound()
    return web.FileResponse(
        avatar_path,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


async def get_leaderboard(request):
    try:
        grade_value = request.query.get("grade")
        grade = int(grade_value) if grade_value else None
        return web.json_response(
            await community_store.leaderboard(request.query.get("period", "day"), grade)
        )
    except (CommunityError, ValueError) as error:
        return _community_error(error)


async def create_enrollment(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        lead = await community_store.create_enrollment(user, payload)
        if ADMIN_ID:
            username = f"@{lead['telegram_username']}" if lead["telegram_username"] else "без username"
            diagnostic = lead.get("diagnostic_score")
            diagnostic_text = f"\nДиагностика: {diagnostic}%" if diagnostic is not None else ""
            await bot.send_message(
                int(ADMIN_ID),
                "📝 Новая заявка на урок\n"
                f"Заявка: {lead['id']}\n"
                f"Ученик: {lead['nickname']} ({username})\n"
                f"Класс: {lead['grade']}\n"
                f"Цель: {lead['goal']}\n"
                f"Частота: {lead['frequency']} раз(а) в неделю"
                f"{diagnostic_text}",
            )
        return web.json_response({"status": "success", "leadId": lead["id"]})
    except CommunityError as error:
        return _community_error(error, status=422)
    except (ValueError, TelegramBadRequest) as error:
        return _community_error(error, status=500)


async def join_battle(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        grade = int(payload.get("grade") or 0)
        questions = [question for question in await _load_questions() if question.grade == grade]
        battle_id = await community_store.join_battle(user, grade, questions)
        question_map = {question.question_id: question for question in questions}
        state = await community_store.battle_state(user, battle_id, question_map)
        return web.json_response(state)
    except (CommunityError, ValueError) as error:
        return _community_error(error, status=422)
    except (QuestionFormatError, aiohttp.ClientError, asyncio.TimeoutError) as error:
        return _community_error(error, status=502)


async def get_battle(request):
    try:
        user = _authenticated_user(request)
        questions = await _load_questions()
        question_map = {question.question_id: question for question in questions}
        return web.json_response(
            await community_store.battle_state(user, request.match_info["battle_id"], question_map)
        )
    except CommunityError as error:
        return _community_error(error, status=404)
    except (QuestionFormatError, aiohttp.ClientError, asyncio.TimeoutError) as error:
        return _community_error(error, status=502)


async def answer_battle(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        questions = await _load_questions()
        question_map = {question.question_id: question for question in questions}
        result = await community_store.answer_battle(
            user,
            request.match_info["battle_id"],
            str(payload.get("questionId") or ""),
            int(payload.get("selectedIndex")),
            question_map,
        )
        return web.json_response(result)
    except (CommunityError, TypeError, ValueError) as error:
        return _community_error(error, status=422)
    except (QuestionFormatError, aiohttp.ClientError, asyncio.TimeoutError) as error:
        return _community_error(error, status=502)
async def get_stats(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({"error": "No user_id"}, status=400)
    
    stats = {"total": 0, "correct": 0, "topics": {}}
    
    # Если файла еще нет, просто возвращаем нули (0%)
    if not os.path.exists(RESULTS_FILE):
        return web.json_response(stats)
        
    try:
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
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
                
    return web.json_response(stats)
def create_app():
    application = web.Application(client_max_size=2 * 1024 * 1024)
    application.router.add_get('/', handle_index)
    application.router.add_get('/app.css', handle_styles)
    application.router.add_get('/community.js', handle_community_script)
    application.router.add_get('/math-format.js', handle_math_script)
    application.router.add_get('/api/questions', get_questions)
    application.router.add_post('/save', save_progress)
    application.router.add_get('/stats', get_stats)
    application.router.add_get('/api/profile', get_profile)
    application.router.add_post('/api/profile', update_profile)
    application.router.add_get('/avatars/{filename}', get_avatar)
    application.router.add_get('/api/leaderboard', get_leaderboard)
    application.router.add_post('/api/enrollments', create_enrollment)
    application.router.add_post('/api/battles/join', join_battle)
    application.router.add_get('/api/battles/{battle_id}', get_battle)
    application.router.add_post('/api/battles/{battle_id}/answer', answer_battle)
    return application


app = create_app()


# === ЗАПУСК ===

async def main():
    if ADMIN_ID:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="admin", description="Панель администратора"),
                    BotCommand(command="sendall", description="Разослать сообщение всем"),
                    BotCommand(command="users", description="Список пользователей"),
                    BotCommand(command="delete_last", description="Удалить последнюю рассылку"),
                ],
                scope=BotCommandScopeChat(chat_id=int(ADMIN_ID)),
            )
        except (
            ValueError,
            TelegramBadRequest,
            TelegramNetworkError,
            TelegramServerError,
            TelegramForbiddenError,
        ):
            print("Не удалось настроить команды администратора")
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
