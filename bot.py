import os
import json
import asyncio
import ssl
import time
from urllib.parse import urlencode

import aiohttp
import certifi
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
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
from drive_questions import fetch_public_drive_index, parse_drive_index
from questions import QuestionFormatError, SUPPORTED_GRADES, parse_questions_csv

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
WEBAPP_VERSION = "14"
ADMIN_ID = os.getenv("ADMIN_ID")
PORT = int(os.getenv("PORT", 8080))
QUESTIONS_CSV_URL = os.getenv(
    "QUESTIONS_CSV_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyYBIArwn-npZYPgPwIazi4HzVR4DzusAc1VvJ_eQklHkYBElS7r0pwZzx-Pe2tPnoop9sFBpFMZWj/pub?output=csv",
)
QUESTIONS_CACHE_TTL = int(os.getenv("QUESTIONS_CACHE_TTL", "60"))
LOCAL_IMAGE_QUESTIONS_FILE = os.getenv("LOCAL_IMAGE_QUESTIONS_FILE", "image_questions.csv")
DRIVE_INDEX_URL = os.getenv("DRIVE_INDEX_URL", "").strip()
DRIVE_ROOT_FOLDER_ID = os.getenv(
    "DRIVE_ROOT_FOLDER_ID", "1CIagfcGHZO_Sdk2G1QysBNg-rX06c_-r"
).strip()

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
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔄 Обновить базу заданий",
                callback_data="admin_refresh_questions",
            )
        ]])
        await message.answer(
            "🛠 Панель администратора\n\n"
            "1. Отправьте боту готовое сообщение: текст, фото, видео, аудио или голосовое.\n"
            "2. Ответьте на это сообщение командой /sendall или /all.\n\n"
            "Также можно отправить: /sendall текст сообщения\n"
            "/users — количество и список пользователей\n"
            "/delete_last — удалить последнюю рассылку у получателей\n"
            "/refresh — обновить Google Таблицу и изображения",
            reply_markup=markup,
        )


def _question_counts(questions):
    counts = {}
    for grade in sorted(SUPPORTED_GRADES):
        grade_questions = [question for question in questions if question.grade == grade]
        images = sum(bool(question.image_url) for question in grade_questions)
        counts[grade] = {
            "total": len(grade_questions),
            "images": images,
            "text": len(grade_questions) - images,
        }
    return counts


async def _refresh_questions_for_admin(message):
    try:
        questions = await _load_questions(force=True)
        counts = _question_counts(questions)
        source_status = (
            "Google Таблица и папки Google Drive"
            if DRIVE_INDEX_URL or DRIVE_ROOT_FOLDER_ID
            else "Google Таблица; папки Google Drive не подключены"
        )
        lines = [
            f"{grade} класс: {values['total']} "
            f"(текстовых: {values['text']}, с картинкой: {values['images']})"
            for grade, values in counts.items()
        ]
        await message.answer(
            "✅ База заданий обновлена\n\n"
            + "\n".join(lines)
            + f"\n\nИсточник: {source_status}."
        )
    except (
        QuestionFormatError,
        aiohttp.ClientError,
        asyncio.TimeoutError,
        OSError,
        ValueError,
    ) as error:
        await message.answer(
            "⚠ Не удалось обновить базу. Рабочая версия сохранена без изменений.\n\n"
            f"Причина: {error}"
        )


@dp.message(Command("refresh"))
async def refresh_questions_command(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("Эта команда доступна только администратору.")
        return
    await message.answer("⏳ Проверяю Google Таблицу и папки с изображениями…")
    await _refresh_questions_for_admin(message)


@dp.callback_query(F.data == "admin_refresh_questions")
async def refresh_questions_button(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.answer("Обновление запущено")
    await callback.message.answer("⏳ Проверяю Google Таблицу и папки с изображениями…")
    await _refresh_questions_for_admin(callback.message)


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
    return web.FileResponse('index.html', headers={"Cache-Control": "no-store, max-age=0"})


async def handle_styles(request):
    return web.FileResponse('app.css', headers={"Cache-Control": "no-store, max-age=0"})


async def handle_community_script(request):
    return web.FileResponse('community.js', headers={"Cache-Control": "no-store, max-age=0"})


async def handle_character_script(request):
    return web.FileResponse('characters.js', headers={"Cache-Control": "no-store, max-age=0"})


async def handle_math_script(request):
    return web.FileResponse('math-format.js', headers={"Cache-Control": "no-store, max-age=0"})


def _authenticated_user(request):
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return validate_telegram_init_data(init_data, TOKEN)


def _community_error(error, status=400):
    return web.json_response({"error": str(error)}, status=status)


async def _load_questions(force=False):
    now = time.monotonic()
    manual_refresh_enabled = bool(DRIVE_INDEX_URL or DRIVE_ROOT_FOLDER_ID)
    if (
        not force
        and questions_cache["items"]
        and (
            manual_refresh_enabled
            or now - questions_cache["loaded_at"] < QUESTIONS_CACHE_TTL
        )
    ):
        return questions_cache["items"]

    async with questions_cache_lock:
        now = time.monotonic()
        if (
            not force
            and questions_cache["items"]
            and (
                manual_refresh_enabled
                or now - questions_cache["loaded_at"] < QUESTIONS_CACHE_TTL
            )
        ):
            return questions_cache["items"]

        separator = "&" if "?" in QUESTIONS_CSV_URL else "?"
        cache_busted_url = f"{QUESTIONS_CSV_URL}{separator}t={int(time.time())}"
        timeout = aiohttp.ClientTimeout(total=30)
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(cache_busted_url) as response:
                response.raise_for_status()
                csv_text = await response.text()

            drive_payload = None
            if DRIVE_INDEX_URL:
                drive_separator = "&" if "?" in DRIVE_INDEX_URL else "?"
                drive_url = f"{DRIVE_INDEX_URL}{drive_separator}t={int(time.time())}"
                async with session.get(drive_url) as response:
                    response.raise_for_status()
                    drive_payload = await response.json(content_type=None)
            elif DRIVE_ROOT_FOLDER_ID:
                try:
                    drive_payload = await fetch_public_drive_index(
                        session, DRIVE_ROOT_FOLDER_ID
                    )
                except (QuestionFormatError, aiohttp.ClientError, asyncio.TimeoutError):
                    if force:
                        raise
                    # On a cold start the verified bundled image set keeps the
                    # bot usable even if Google Drive is temporarily unavailable.
                    drive_payload = None

        questions = parse_questions_csv(csv_text)
        # Files 1–5 are the verified legacy set. The Drive parser ignores these
        # numeric-only filenames and adds only new files following "6 - answer".
        if os.path.exists(LOCAL_IMAGE_QUESTIONS_FILE):
            with open(LOCAL_IMAGE_QUESTIONS_FILE, "r", encoding="utf-8") as source:
                questions.extend(parse_questions_csv(source.read()))
        if drive_payload is not None:
            questions.extend(parse_drive_index(drive_payload))
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


async def claim_daily_login(request):
    try:
        return web.json_response(await community_store.claim_daily_login(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=401)


async def award_training_coins(request):
    try:
        payload = await request.json()
        return web.json_response(await community_store.award_training_coins(
            _authenticated_user(request), payload.get("attemptKey")
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


async def get_characters(request):
    try:
        return web.json_response(await community_store.character_catalog(
            _authenticated_user(request)
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


async def select_character(request):
    try:
        payload = await request.json()
        return web.json_response(await community_store.select_character(
            _authenticated_user(request), payload.get("characterId")
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


async def purchase_character(request):
    try:
        payload = await request.json()
        return web.json_response(await community_store.purchase_character(
            _authenticated_user(request), payload.get("characterId")
        ))
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


def _social_webapp_url(route_params=None):
    params = {"v": WEBAPP_VERSION}
    params.update({
        str(key): str(value)
        for key, value in (route_params or {}).items()
        if value is not None and str(value)
    })
    separator = "&" if "?" in WEBAPP_URL else "?"
    return f"{WEBAPP_URL}{separator}{urlencode(params)}"


async def _notify_social_user(
    user_id,
    text,
    button_text="Открыть приложение",
    route_params=None,
):
    if not WEBAPP_URL:
        return
    try:
        await bot.send_message(
            int(user_id),
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text=button_text,
                web_app=WebAppInfo(url=_social_webapp_url(route_params)),
            )]]),
        )
    except (
        ValueError,
        TelegramBadRequest,
        TelegramForbiddenError,
        TelegramNetworkError,
        TelegramServerError,
    ):
        pass


async def get_participant(request):
    try:
        user = _authenticated_user(request)
        return web.json_response(
            await community_store.participant(user, request.match_info["public_id"])
        )
    except CommunityError as error:
        return _community_error(error, status=404)


async def search_participants(request):
    try:
        return web.json_response(await community_store.search_participants(
            _authenticated_user(request), request.query.get("q", "")
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


async def get_friends(request):
    try:
        return web.json_response(await community_store.friends(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=401)


async def request_friend(request):
    try:
        user = _authenticated_user(request)
        result = await community_store.request_friend(user, request.match_info["public_id"])
        target_user_id = result.pop("targetUserId", None)
        request_id = result.get("requestId")
        profile = await community_store.get_profile(user)
        if target_user_id:
            if result["status"] == "accepted":
                text = f"✅ Вы и {profile.get('nickname', 'участник')} теперь друзья."
                button = "Открыть друзей"
            else:
                text = f"👋 {profile.get('nickname', 'Участник')} хочет добавить вас в друзья."
                button = "Посмотреть заявку"
            await _notify_social_user(
                target_user_id,
                text,
                button,
                {"view": "friends", "request": request_id},
            )
        return web.json_response(result)
    except CommunityError as error:
        return _community_error(error, status=422)


async def accept_friend(request):
    try:
        user = _authenticated_user(request)
        result = await community_store.accept_friend(user, request.match_info["request_id"])
        target_user_id = result.pop("targetUserId", None)
        profile = await community_store.get_profile(user)
        if target_user_id:
            await _notify_social_user(
                target_user_id,
                f"✅ {profile.get('nickname', 'Участник')} принял(а) вашу заявку в друзья.",
                "Открыть друзей",
                {"view": "friends"},
            )
        return web.json_response(result)
    except CommunityError as error:
        return _community_error(error, status=422)


async def decline_friend(request):
    try:
        return web.json_response(await community_store.decline_friend(
            _authenticated_user(request), request.match_info["request_id"]
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


async def get_messages(request):
    try:
        return web.json_response(await community_store.conversation(
            _authenticated_user(request), request.match_info["public_id"]
        ))
    except CommunityError as error:
        return _community_error(error, status=403)


async def send_message(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        result = await community_store.send_message(
            user, request.match_info["public_id"], payload.get("text")
        )
        target_user_id = result.pop("targetUserId", None)
        profile = await community_store.get_profile(user)
        if target_user_id:
            await _notify_social_user(
                target_user_id,
                f"💬 Новое сообщение от {profile.get('nickname', 'друга')}.",
                "Открыть сообщения",
                {"view": "chat", "publicId": profile.get("public_id")},
            )
        return web.json_response(result)
    except CommunityError as error:
        return _community_error(error, status=422)


async def get_battle_invites(request):
    try:
        return web.json_response(await community_store.battle_invites(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=401)


async def create_battle_invite(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        result = await community_store.create_battle_invite(
            user, payload.get("publicId"), payload.get("grade")
        )
        target_user_id = result.pop("targetUserId", None)
        profile = await community_store.get_profile(user)
        if target_user_id:
            await _notify_social_user(
                target_user_id,
                f"⚔️ {profile.get('nickname', 'Друг')} приглашает вас в баттл за {int(payload.get('grade'))} класс.",
                "Принять вызов",
                {"view": "battle-invite", "invite": result.get("inviteId")},
            )
        return web.json_response(result)
    except (CommunityError, TypeError, ValueError) as error:
        return _community_error(error, status=422)


async def accept_battle_invite(request):
    try:
        user = _authenticated_user(request)
        invites = await community_store.battle_invites(user)
        invite = next((
            item for item in invites["incoming"]
            if item["id"] == request.match_info["invite_id"]
        ), None)
        if not invite:
            raise CommunityError("Приглашение в баттл не найдено или устарело")
        questions = [
            question for question in await _load_questions()
            if question.grade == int(invite["grade"])
        ]
        result = await community_store.accept_battle_invite(
            user, request.match_info["invite_id"], questions
        )
        target_user_id = result.pop("targetUserId", None)
        profile = await community_store.get_profile(user)
        if target_user_id:
            await _notify_social_user(
                target_user_id,
                f"🔥 {profile.get('nickname', 'Друг')} принял(а) вызов. Баттл начался!",
                "Открыть баттл",
                {"view": "battle", "battle": result["battleId"]},
            )
        question_map = {question.question_id: question for question in questions}
        state = await community_store.battle_state(user, result["battleId"], question_map)
        return web.json_response(state)
    except (CommunityError, TypeError, ValueError) as error:
        return _community_error(error, status=422)
    except (QuestionFormatError, aiohttp.ClientError, asyncio.TimeoutError) as error:
        return _community_error(error, status=502)


async def decline_battle_invite(request):
    try:
        return web.json_response(await community_store.decline_battle_invite(
            _authenticated_user(request), request.match_info["invite_id"]
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


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
    application.router.add_get('/characters.js', handle_character_script)
    application.router.add_get('/math-format.js', handle_math_script)
    application.router.add_static('/assets/', 'assets', show_index=False)
    application.router.add_get('/api/questions', get_questions)
    application.router.add_post('/save', save_progress)
    application.router.add_get('/stats', get_stats)
    application.router.add_get('/api/profile', get_profile)
    application.router.add_post('/api/profile', update_profile)
    application.router.add_post('/api/daily-login', claim_daily_login)
    application.router.add_post('/api/coins/training', award_training_coins)
    application.router.add_get('/api/characters', get_characters)
    application.router.add_post('/api/characters/select', select_character)
    application.router.add_post('/api/characters/purchase', purchase_character)
    application.router.add_get('/avatars/{filename}', get_avatar)
    application.router.add_get('/api/leaderboard', get_leaderboard)
    application.router.add_get('/api/participants/search', search_participants)
    application.router.add_get('/api/participants/{public_id}', get_participant)
    application.router.add_get('/api/friends', get_friends)
    application.router.add_post('/api/friends/{public_id}', request_friend)
    application.router.add_post('/api/friend-requests/{request_id}/accept', accept_friend)
    application.router.add_post('/api/friend-requests/{request_id}/decline', decline_friend)
    application.router.add_get('/api/messages/{public_id}', get_messages)
    application.router.add_post('/api/messages/{public_id}', send_message)
    application.router.add_get('/api/battle-invites', get_battle_invites)
    application.router.add_post('/api/battle-invites', create_battle_invite)
    application.router.add_post('/api/battle-invites/{invite_id}/accept', accept_battle_invite)
    application.router.add_post('/api/battle-invites/{invite_id}/decline', decline_battle_invite)
    application.router.add_post('/api/enrollments', create_enrollment)
    application.router.add_post('/api/battles/join', join_battle)
    application.router.add_get('/api/battles/{battle_id}', get_battle)
    application.router.add_post('/api/battles/{battle_id}/answer', answer_battle)
    return application


app = create_app()


# === ЗАПУСК ===

async def main():
    # Бот получает обновления через polling. Удаляем webhook, который мог
    # остаться от прежнего хостинга, не отбрасывая уже ожидающие сообщения.
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Прокачать матан",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}?v={WEBAPP_VERSION}"),
            )
        )
    except (
        TelegramBadRequest,
        TelegramNetworkError,
        TelegramServerError,
        TelegramForbiddenError,
    ):
        print("Не удалось обновить кнопку мини-приложения")
    if ADMIN_ID:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="admin", description="Панель администратора"),
                    BotCommand(command="sendall", description="Разослать сообщение всем"),
                    BotCommand(command="refresh", description="Обновить базу заданий"),
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
