import os
import json
import asyncio
import base64
import ssl
import time
import random
import re
import tempfile
from collections import OrderedDict, deque
from datetime import datetime, timezone
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
from student_learning import (
    ALLOWED_STUDENT_FILE_TYPES,
    MAX_STUDENT_FILE_BYTES,
    StudentLearningError,
    StudentLearningStore,
)
from drive_questions import (
    fetch_expert_game_index,
    fetch_public_drive_index,
    parse_drive_index,
    parse_expert_game_index_report,
    parse_extended_drive_index,
)
from questions import QuestionFormatError, SUPPORTED_GRADES, parse_questions_csv

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
WEBAPP_VERSION = "46"
ADMIN_ID = os.getenv("ADMIN_ID")
MATHPIX_APP_ID = os.getenv("MATHPIX_APP_ID", "").strip()
MATHPIX_APP_KEY = os.getenv("MATHPIX_APP_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_GRADER_MODEL = os.getenv("OPENAI_GRADER_MODEL", "gpt-5-mini").strip()
ADMIN_USERNAMES = {
    value.strip().lstrip("@").casefold()
    for value in os.getenv("ADMIN_USERNAMES", "supertutor15,Dany_german").split(",")
    if value.strip()
}


def is_admin_telegram_user(user):
    return bool(user) and (
        str(user.id) == str(ADMIN_ID)
        or str(getattr(user, "username", "") or "").casefold() in ADMIN_USERNAMES
    )
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
EXPERT_GAME_FOLDER_ID = os.getenv(
    "EXPERT_GAME_FOLDER_ID", "10zrD0b4U64JFALp6lUqjzaZl9Gn1DYzN"
).strip()
EXPERT_GAME_MAX_SCORE = int(os.getenv("EXPERT_GAME_MAX_SCORE", "2"))
bot = Bot(token=TOKEN)
dp = Dispatcher()

# === ПУТИ К ФАЙЛАМ (С учетом Railway) ===
# Если есть несгораемый диск Railway (/data), используем его. Иначе сохраняем в текущую папку.
DATA_DIR = "/data" if os.path.exists("/data") else "."
USERS_FILE = f"{DATA_DIR}/users.json"
BROADCAST_FILE = f"{DATA_DIR}/last_broadcast.json"
RESULTS_FILE = f"{DATA_DIR}/results.json" # Сюда будут падать результаты из WebApp
COMMUNITY_FILE = f"{DATA_DIR}/community.json"
STUDENT_LEARNING_FILE = f"{DATA_DIR}/student_learning.json"

community_store = CommunityStore(COMMUNITY_FILE)
student_learning_store = StudentLearningStore(STUDENT_LEARNING_FILE)
admin_student_flows = {}

questions_cache = {
    "loaded_at": 0.0,
    "items": [],
    "extended": {grade: [] for grade in SUPPORTED_GRADES},
    "expert": {},
    "expert_warnings": [],
}
questions_cache_lock = asyncio.Lock()

GRADE_AGE_GROUPS = {
    8: "13–15 лет",
    9: "14–16 лет",
    10: "15–17 лет",
    11: "16–18 лет",
}


def save_user(user):
    user_id = int(getattr(user, "id", user))
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as source:
                stored = json.load(source)
            if isinstance(stored, dict):
                users = stored
            elif isinstance(stored, list):
                users = {str(value): {} for value in stored}
        except (OSError, ValueError, TypeError):
            users = {}
    record = users.setdefault(str(user_id), {})
    if hasattr(user, "id"):
        record.update({
            "name": " ".join(filter(None, [
                str(getattr(user, "first_name", "") or "").strip(),
                str(getattr(user, "last_name", "") or "").strip(),
            ])).strip(),
            "username": str(getattr(user, "username", "") or "").lstrip("@"),
        })
    with open(USERS_FILE, "w", encoding="utf-8") as target:
        json.dump(users, target, ensure_ascii=False, indent=2)


def build_users_report(users, community_data):
    """Build an admin-only class/age-group report without storing birth dates."""
    if isinstance(users, dict):
        records = {
            str(user_id): info if isinstance(info, dict) else {}
            for user_id, info in users.items()
        }
    else:
        records = {str(user_id): {} for user_id in (users or [])}
    profiles = community_data.get("profiles", {}) if isinstance(community_data, dict) else {}
    class_counts = {grade: 0 for grade in SUPPORTED_GRADES}
    unknown_count = 0
    rows = []
    for user_id in sorted(
        records,
        key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
    ):
        stored = records[user_id]
        profile = profiles.get(user_id, {}) if isinstance(profiles, dict) else {}
        name = stored.get("name") or profile.get("nickname") or "Без имени"
        username_value = stored.get("username") or profile.get("telegram_username") or ""
        username = f"@{username_value}" if username_value else "Нет @username"
        try:
            grade = int(profile.get("grade"))
        except (TypeError, ValueError):
            grade = None
        if grade in class_counts:
            class_counts[grade] += 1
            class_label = f"{grade} класс"
            age_label = f"ориентировочно {GRADE_AGE_GROUPS[grade]}"
        else:
            unknown_count += 1
            class_label = "класс не выбран"
            age_label = "возрастная группа неизвестна"
        rows.append(
            f"ID: {user_id} | Имя: {name} | ТГ: {username} | "
            f"{class_label} | {age_label}"
        )

    leaders = []
    if class_counts and max(class_counts.values(), default=0) > 0:
        maximum = max(class_counts.values())
        leaders = [str(grade) for grade, count in class_counts.items() if count == maximum]
    summary = [
        f"{grade} класс · ориентировочно {GRADE_AGE_GROUPS[grade]}: {class_counts[grade]} чел."
        for grade in sorted(SUPPORTED_GRADES)
    ]
    summary.append(f"Класс ещё не выбран: {unknown_count} чел.")
    if leaders:
        summary.append(f"Больше всего пользователей: {' и '.join(leaders)} класс.")
    return (
        f"📊 Всего в боте: {len(records)} чел.\n"
        "Возрастные группы рассчитаны ориентировочно по выбранному классу; "
        "даты рождения бот не собирает.\n\n"
        "РАСПРЕДЕЛЕНИЕ ПО КЛАССАМ\n"
        + "\n".join(summary)
        + "\n\nПОЛЬЗОВАТЕЛИ\n"
        + ("\n".join(rows) if rows else "Пользователей пока нет.")
        + "\n"
    )


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
    save_user(message.from_user)
    # Сбрасываем кэш, чтобы у пользователей всегда открывалась свежая версия приложения
    safe_url = f"{WEBAPP_URL}?v={int(time.time())}"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Прокачать матан", web_app=WebAppInfo(url=safe_url))]
    ])
    await message.answer(f"Привет, {message.from_user.first_name}! 👋\nЖми кнопку ниже!", reply_markup=markup)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if is_admin_telegram_user(message.from_user):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Обновить базу заданий",
                callback_data="admin_refresh_questions",
            )],
            [InlineKeyboardButton(
                text="👥 Пользователи по классам",
                callback_data="admin_users_report",
            )],
            [InlineKeyboardButton(
                text="🎓 Добавить ученика",
                callback_data="admin_student_add",
            )],
            [InlineKeyboardButton(
                text="✏️ Изменить данные ученика",
                callback_data="admin_student_edit",
            )],
            [InlineKeyboardButton(
                text="📄 Добавить конспект урока",
                callback_data="admin_student_lesson",
            )],
            [InlineKeyboardButton(
                text="✅ Проверить ДЗ",
                callback_data="admin_student_homework",
            )],
        ])
        await message.answer(
            "🛠 Панель администратора\n\n"
            "1. Отправьте боту готовое сообщение: текст, фото, видео, аудио или голосовое.\n"
            "2. Ответьте на это сообщение командой /sendall или /all.\n\n"
            "Также можно отправить: /sendall текст сообщения\n"
            "/users — пользователи, классы и возрастные группы\n"
            "/delete_last — удалить последнюю рассылку у получателей\n"
            "/refresh — обновить тренировки, вторую часть и игру «Ты — эксперт»\n\n"
            "Персональные кабинеты создаются кнопкой «Добавить ученика». Пароль показывается один раз.",
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
            f"(текстовых: {values['text']}, с картинкой: {values['images']}, "
            f"2 часть: {len(questions_cache.get('extended', {}).get(grade, []))})"
            for grade, values in counts.items()
        ]
        expert_banks = questions_cache.get("expert", {})
        expert_lines = [
            f"{grade} класс: " + (
                "; ".join(
                    f"{number} номер — {len(tasks)} работ"
                    for number, tasks in sorted(expert_banks.get(grade, {}).items())
                    if tasks
                ) or "нет готовых работ"
            )
            for grade in sorted(SUPPORTED_GRADES)
        ]
        warnings = questions_cache.get("expert_warnings", [])
        warning_text = (
            "\n\n⚠ Пропущены незавершённые папки:\n"
            + "\n".join(f"• {warning}" for warning in warnings[:7])
            if warnings else ""
        )
        await message.answer(
            "✅ База заданий обновлена\n\n"
            + "\n".join(lines)
            + "\n\nИгра «Ты — эксперт»:\n"
            + "\n".join(expert_lines)
            + warning_text
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
    if not is_admin_telegram_user(message.from_user):
        await message.answer("Эта команда доступна только администратору.")
        return
    await message.answer("⏳ Обновляю тренировки, вторую часть и игру «Ты — эксперт»…")
    await _refresh_questions_for_admin(message)


@dp.callback_query(F.data == "admin_refresh_questions")
async def refresh_questions_button(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.answer("Обновление запущено")
    await callback.message.answer("⏳ Обновляю тренировки, вторую часть и игру «Ты — эксперт»…")
    await _refresh_questions_for_admin(callback.message)


@dp.message(Command("sendall", "all"))
async def broadcast_command(message: types.Message):
    if not is_admin_telegram_user(message.from_user):
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
    if not is_admin_telegram_user(message.from_user):
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
    if not is_admin_telegram_user(message.from_user):
        return
    await _send_users_report(message)


async def _send_users_report(message):
    if not os.path.exists(USERS_FILE):
        await message.answer("⚠ База пользователей пока пуста.")
        return

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        await message.answer("⚠ Ошибка чтения файла.")
        return

    async with community_store.lock:
        community_data = community_store._load()

    # Создаем временный файл-отчет
    report_path = f"{DATA_DIR}/users_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(build_users_report(users, community_data))

    # Отправляем файл пользователю
    doc = FSInputFile(report_path)
    await message.answer_document(doc, caption="👥 Пользователи по классам и возрастным группам")


@dp.callback_query(F.data == "admin_users_report")
async def users_report_button(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.answer("Формирую отчёт")
    await _send_users_report(callback.message)


def _student_keyboard(students, prefix):
    rows = []
    for student in students:
        rows.append([InlineKeyboardButton(
            text=f"{student['displayName']} · {student['grade']} класс",
            callback_data=f"{prefix}:{student['id']}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _student_lesson_mode_keyboard(student_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✍️ Заполнить тест и ДЗ вручную",
            callback_data=f"student_lesson_mode:manual:{student_id}",
        )],
        [InlineKeyboardButton(
            text="🤖 Сгенерировать автоматически",
            callback_data=f"student_lesson_mode:auto:{student_id}",
        )],
    ])


def _clean_numbered_admin_field(value, label_pattern=None):
    """Accept both plain fields and the numbered template shown to the admin."""
    cleaned = re.sub(r"^(?:\s*\d+\s*[.)]\s*)+", "", str(value or "").strip())
    if label_pattern:
        cleaned = re.sub(
            rf"^(?:{label_pattern})\s*[:=\-–—]?\s*",
            "",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
    return cleaned.strip()


def parse_admin_student_fields(text):
    """Parse the seven-line admin form without treating list numbers as data."""
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if len(lines) != 7:
        raise StudentLearningError(
            "Нужно прислать ровно 7 заполненных строк. Проверьте формат и повторите или отправьте /cancel."
        )

    username = _clean_numbered_admin_field(
        lines[0], r"(?:telegram\s*)?(?:username|юзернейм|юз)"
    )
    username_match = re.fullmatch(r"@?([A-Za-z0-9_]{5,32})", username)
    if not username_match:
        raise StudentLearningError(
            "Первая строка должна содержать Telegram username, например @whitarrr"
        )

    grade = _clean_numbered_admin_field(lines[1], r"класс")
    grade_match = re.fullmatch(r"(8|9|10|11)(?:\s*класс)?", grade, flags=re.IGNORECASE)
    if not grade_match:
        raise StudentLearningError("Во второй строке укажите класс: 8, 9, 10 или 11")

    return {
        "username": username_match.group(1),
        "grade": grade_match.group(1),
        "display_name": _clean_numbered_admin_field(lines[2], r"имя(?:\s+для\s+кабинета)?"),
        "goal": _clean_numbered_admin_field(lines[3], r"глобальная\s+цель(?:\s+на\s+год)?"),
        "facts": _clean_numbered_admin_field(lines[4], r"важные\s+факты(?:\s+и\s+особенности)?"),
        "lesson_schedule": _clean_numbered_admin_field(lines[5], r"дни\s+и\s+время(?:\s+(?:уроков|занятий))?"),
        "reminder_time": _clean_numbered_admin_field(lines[6], r"время(?:\s+ежедневного)?\s+напоминания"),
    }


def parse_manual_lesson_content(text):
    """Parse a teacher-authored lesson package from a Telegram message."""
    value = str(text or "").strip()
    if not value or len(value) > 50_000:
        raise StudentLearningError("Сообщение с тестом и ДЗ пустое или слишком длинное")

    lines = [line.strip() for line in value.splitlines()]
    homework_index = next((
        index for index, line in enumerate(lines)
        if re.fullmatch(r"(?:дз|домашнее\s+задание)\s*:?", line, flags=re.IGNORECASE)
    ), None)
    test_index = next((
        index for index, line in enumerate(lines)
        if re.fullmatch(r"тест\s*:?", line, flags=re.IGNORECASE)
    ), None)
    if homework_index is None or test_index is None or homework_index >= test_index:
        raise StudentLearningError("Добавьте отдельные разделы «ДЗ:» и «ТЕСТ:» по образцу")

    title = ""
    next_topic = ""
    for line in lines[:homework_index]:
        title_match = re.match(r"^тема(?:\s+урока)?\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        next_match = re.match(r"^следующая\s+тема\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
        elif next_match:
            next_topic = next_match.group(1).strip()
    if not title:
        raise StudentLearningError("В начале сообщения укажите «Тема: …»")

    homework_tasks = []
    for line in lines[homework_index + 1:test_index]:
        cleaned = re.sub(r"^(?:\d+\s*[.)]|[-•])\s*", "", line).strip()
        if cleaned:
            homework_tasks.append(cleaned)
    if not homework_tasks:
        raise StudentLearningError("Добавьте хотя бы одно задание в раздел «ДЗ»")
    if len(homework_tasks) > 50:
        raise StudentLearningError("В одном ДЗ может быть не больше 50 заданий")

    question_blocks = []
    current = None
    for line in lines[test_index + 1:]:
        if not line:
            continue
        question_match = re.match(r"^(\d+)\s*[.)]\s*(.+)$", line)
        if question_match:
            if current:
                question_blocks.append(current)
            current = {"question": question_match.group(2).strip(), "options": [], "answer": None, "explanation": ""}
            continue
        if current is None:
            continue
        option_match = re.match(r"^([A-DА-Г])\s*[).:]\s*(.+)$", line, flags=re.IGNORECASE)
        if option_match:
            current["options"].append((option_match.group(1).upper(), option_match.group(2).strip()))
            continue
        answer_match = re.match(r"^ответ\s*:\s*([A-DА-Г1-4])\s*$", line, flags=re.IGNORECASE)
        if answer_match:
            current["answer"] = answer_match.group(1).upper()
            continue
        explanation_match = re.match(r"^пояснение\s*:\s*(.*)$", line, flags=re.IGNORECASE)
        if explanation_match:
            current["explanation"] = explanation_match.group(1).strip()
            continue
        if current["explanation"]:
            current["explanation"] += " " + line
        else:
            current["question"] += " " + line
    if current:
        question_blocks.append(current)
    if not question_blocks:
        raise StudentLearningError("Добавьте хотя бы один вопрос в раздел «ТЕСТ»")
    if len(question_blocks) > 30:
        raise StudentLearningError("В одном тесте может быть не больше 30 вопросов")

    answer_map = {"A": 0, "А": 0, "B": 1, "Б": 1, "C": 2, "В": 2, "D": 3, "Г": 3,
                  "1": 0, "2": 1, "3": 2, "4": 3}
    test_questions = []
    for index, block in enumerate(question_blocks, 1):
        if len(block["options"]) != 4:
            raise StudentLearningError(f"В вопросе {index} должно быть ровно 4 варианта: А, Б, В и Г")
        answer_index = answer_map.get(block["answer"])
        if answer_index is None:
            raise StudentLearningError(f"В вопросе {index} укажите строку «Ответ: А/Б/В/Г»")
        option_labels = [label for label, _ in block["options"]]
        expected_labels = [{"A", "А"}, {"B", "Б"}, {"C", "В"}, {"D", "Г"}]
        if any(label not in allowed for label, allowed in zip(option_labels, expected_labels)):
            raise StudentLearningError(f"В вопросе {index} расположите варианты по порядку: А, Б, В, Г")
        test_questions.append({
            "question": block["question"][:2000],
            "options": [option[:1000] for _, option in block["options"]],
            "correct_index": answer_index,
            "explanation": block["explanation"][:2000],
        })

    return {
        "title": title[:160],
        "next_topic": next_topic[:500],
        "homework_tasks": homework_tasks,
        "test_questions": test_questions,
        "generation_status": "manual",
    }


def parse_manual_test_content(text, fallback_title=""):
    """Parse a teacher-authored test copied from a message or extracted from a PDF."""
    value = str(text or "").replace("\xa0", " ").replace("\r", "\n").strip()
    if not value or len(value) > 60_000:
        raise StudentLearningError("Тест пустой или слишком длинный")

    # Keep the PDF's line boundaries intact. Splitting on numbered fragments
    # would turn explanatory text such as "Шаг 2." into a fake question.
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]

    def looks_like_question_start(line_index, expected_number):
        match = re.match(r"^(\d{1,2})\s*[.)]\s*(.+)$", lines[line_index])
        if not match or int(match.group(1)) != expected_number:
            return None
        expected_options = [{"A", "А"}, {"B", "Б"}, {"C", "В"}, {"D", "Г"}]
        option_position = 0
        for candidate in lines[line_index + 1:line_index + 11]:
            option = re.match(r"^([A-DА-Г])\s*[).:]\s*(.+)$", candidate, flags=re.IGNORECASE)
            if option and option_position < 4 and option.group(1).upper() in expected_options[option_position]:
                option_position += 1
                if option_position == 4:
                    return match
            elif re.match(r"^\d{1,2}\s*[.)]\s*", candidate):
                break
        return None

    title = ""
    next_topic = ""
    question_blocks = []
    current = None
    active_field = "question"
    preamble = []

    for line_index, line in enumerate(lines):
        if not line:
            continue
        if re.fullmatch(r"стр\.?\s*\d+", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r".+\s+[·|]\s+\d{1,2}\s+класс", line, flags=re.IGNORECASE):
            continue
        title_match = re.match(r"^тема(?:\s+урока)?\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        next_match = re.match(r"^следующая\s+тема\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if current is None and title_match:
            title = title_match.group(1).strip()
            continue
        if current is None and next_match:
            next_topic = next_match.group(1).strip()
            continue
        if current is None and re.fullmatch(r"тест(?:\s+по\s+.+)?\s*: ?", line, flags=re.IGNORECASE):
            continue

        expected_number = len(question_blocks) + (2 if current else 1)
        question_match = looks_like_question_start(line_index, expected_number)
        if question_match:
            if current:
                question_blocks.append(current)
            current = {
                "question": question_match.group(2).strip(),
                "options": [],
                "answer": None,
                "explanation": "",
            }
            active_field = "question"
            continue
        if current is None:
            preamble.append(line)
            continue

        option_match = re.match(r"^([A-DА-Г])\s*[).:]\s*(.+)$", line, flags=re.IGNORECASE)
        if option_match:
            current["options"].append([option_match.group(1).upper(), option_match.group(2).strip()])
            active_field = "option"
            continue
        answer_match = re.match(
            r"^(?:правильный\s+)?ответ\s*[:.]\s*([A-DА-Г1-4])(?:\s*[).:]?\s*.*)?$",
            line,
            flags=re.IGNORECASE,
        )
        if answer_match:
            current["answer"] = answer_match.group(1).upper()
            active_field = "answer"
            continue
        explanation_match = re.match(
            r"^(?:подробн(?:ое|ый)\s+)?(?:пояснение|объяснение|разбор)\s*:?\s*(.*)$",
            line,
            flags=re.IGNORECASE,
        )
        if explanation_match:
            current["explanation"] = explanation_match.group(1).strip()
            active_field = "explanation"
            continue
        if active_field == "explanation":
            current["explanation"] = f"{current['explanation']} {line}".strip()
        elif active_field == "option" and current["options"]:
            current["options"][-1][1] = f"{current['options'][-1][1]} {line}".strip()
        else:
            current["question"] = f"{current['question']} {line}".strip()

    if current:
        question_blocks.append(current)
    if not question_blocks:
        raise StudentLearningError(
            "Не нашёл вопросы. Начните каждый со строки «1. …», «2. …» и так далее"
        )
    if len(question_blocks) > 30:
        raise StudentLearningError("В одном тесте может быть не больше 30 вопросов")

    answer_map = {
        "A": 0, "А": 0, "B": 1, "Б": 1, "C": 2, "В": 2, "D": 3, "Г": 3,
        "1": 0, "2": 1, "3": 2, "4": 3,
    }
    expected_labels = [{"A", "А"}, {"B", "Б"}, {"C", "В"}, {"D", "Г"}]
    test_questions = []
    for index, block in enumerate(question_blocks, 1):
        if len(block["options"]) != 4:
            raise StudentLearningError(f"В вопросе {index} должно быть ровно 4 варианта: А, Б, В и Г")
        labels = [option[0] for option in block["options"]]
        if any(label not in allowed for label, allowed in zip(labels, expected_labels)):
            raise StudentLearningError(f"В вопросе {index} расположите варианты по порядку: А, Б, В, Г")
        answer_index = answer_map.get(block["answer"])
        if answer_index is None:
            raise StudentLearningError(f"В вопросе {index} укажите строку «Ответ: А/Б/В/Г»")
        if not block["explanation"]:
            raise StudentLearningError(
                f"В вопросе {index} добавьте строку «Пояснение: …» — она покажется при ошибке"
            )
        test_questions.append({
            "question": block["question"][:2000],
            "options": [option[:1000] for _, option in block["options"]],
            "correct_index": answer_index,
            "explanation": block["explanation"][:2000],
        })

    inferred_title = next((line for line in preamble if re.search(r"\bтест\b", line, flags=re.IGNORECASE)), "")
    if not inferred_title:
        inferred_title = next((
            line for line in preamble
            if not re.fullmatch(r"тест\s*: ?", line, flags=re.IGNORECASE)
        ), "")
    return {
        "title": (title or inferred_title or str(fallback_title or "").strip() or "Тест по уроку")[:160],
        "next_topic": next_topic[:500],
        "test_questions": test_questions,
        "generation_status": "manual",
    }


def parse_manual_homework_content(text):
    """Parse homework supplied as a plain Telegram message."""
    value = str(text or "").replace("\xa0", " ").strip()
    if not value or len(value) > 50_000:
        raise StudentLearningError("ДЗ пустое или слишком длинное")
    tasks = []
    for line in value.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned or re.fullmatch(r"(?:дз|домашнее\s+задание)\s*: ?", cleaned, flags=re.IGNORECASE):
            continue
        cleaned = re.sub(r"^(?:\d+\s*[.)]|[-•])\s*", "", cleaned).strip()
        if cleaned:
            tasks.append(cleaned)
    if not tasks:
        raise StudentLearningError("Добавьте хотя бы одно задание")
    if len(tasks) > 50:
        raise StudentLearningError("В одном ДЗ может быть не больше 50 заданий")
    return tasks


@dp.callback_query(F.data == "admin_student_add")
async def admin_student_add(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    admin_student_flows[str(callback.from_user.id)] = {"kind": "add_student"}
    await callback.answer()
    await callback.message.answer(
        "Пришлите данные одним сообщением, каждая строка отдельно:\n\n"
        "1. @username ученика\n"
        "2. Класс: 8, 9, 10 или 11\n"
        "3. Имя для кабинета\n"
        "4. Глобальная цель на год\n"
        "5. Важные факты и особенности\n"
        "6. Дни и время уроков\n"
        "7. Время ежедневного напоминания в формате ЧЧ:ММ\n\n"
        "Отмена: /cancel"
    )


@dp.callback_query(F.data == "admin_student_lesson")
async def admin_student_lesson(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    students = await student_learning_store.list_students()
    await callback.answer()
    if not students:
        await callback.message.answer("Сначала добавьте хотя бы одного ученика.")
        return
    await callback.message.answer("Выберите ученика для нового конспекта:", reply_markup=_student_keyboard(students, "student_lesson"))


@dp.callback_query(F.data == "admin_student_edit")
async def admin_student_edit(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    students = await student_learning_store.list_students()
    await callback.answer()
    if not students:
        await callback.message.answer("Сначала добавьте хотя бы одного ученика.")
        return
    await callback.message.answer("Выберите ученика:", reply_markup=_student_keyboard(students, "student_edit"))


@dp.callback_query(F.data.startswith("student_edit:"))
async def admin_student_edit_choice(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    student_id = callback.data.split(":", 1)[1]
    students = await student_learning_store.list_students()
    student = next((item for item in students if item["id"] == student_id), None)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    admin_student_flows[str(callback.from_user.id)] = {"kind": "edit_student", "student_id": student_id}
    await callback.answer()
    await callback.message.answer(
        "Пришлите обновлённые данные шестью строками:\n\n"
        f"1. Класс (сейчас: {student['grade']})\n"
        f"2. Имя (сейчас: {student['displayName']})\n"
        f"3. Глобальная цель (сейчас: {student['goal']})\n"
        f"4. Важные учебные факты (сейчас: {student['facts'] or 'не указаны'})\n"
        f"5. Дни и время занятий (сейчас: {student['lessonSchedule']})\n"
        f"6. Время напоминания (сейчас: {student['reminderTime'] or 'не указано'})\n\n"
        "Username и привязанный Telegram ID этим действием не меняются. Отмена: /cancel"
    )


@dp.callback_query(F.data.startswith("student_lesson:"))
async def admin_student_lesson_choice(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    student_id = callback.data.split(":", 1)[1]
    students = await student_learning_store.list_students()
    student = next((item for item in students if item["id"] == student_id), None)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        f"Как подготовить тест и ДЗ для {student['displayName']}?",
        reply_markup=_student_lesson_mode_keyboard(student_id),
    )


@dp.callback_query(F.data.startswith("student_lesson_mode:"))
async def admin_student_lesson_mode(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    _, mode, student_id = callback.data.split(":", 2)
    if mode not in {"manual", "auto"}:
        await callback.answer("Неизвестный режим", show_alert=True)
        return
    students = await student_learning_store.list_students()
    student = next((item for item in students if item["id"] == student_id), None)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    admin_student_flows[str(callback.from_user.id)] = {
        "kind": "lesson_pdf", "student_id": student_id, "mode": mode,
    }
    await callback.answer()
    if mode == "manual":
        description = (
            "После конспекта бот сначала попросит тест, а затем ДЗ. "
            "Каждую часть можно прислать текстом или PDF. "
            "OpenAI API не понадобится."
        )
    else:
        description = (
            "В подписи при желании напишите тему следующего урока. "
            "Для этого режима нужен работающий OpenAI API."
        )
    await callback.message.answer(
        f"Прикрепите PDF-конспект для {student['displayName']}.\n{description}\n\nОтмена: /cancel"
    )


@dp.callback_query(F.data == "admin_student_homework")
async def admin_student_homework(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    students = await student_learning_store.list_students()
    await callback.answer()
    if not students:
        await callback.message.answer("Ученики пока не добавлены.")
        return
    await callback.message.answer("Чьё домашнее задание открыть?", reply_markup=_student_keyboard(students, "student_homework"))


@dp.callback_query(F.data.startswith("student_homework:"))
async def admin_student_homework_choice(callback: types.CallbackQuery):
    if not is_admin_telegram_user(callback.from_user):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    student_id = callback.data.split(":", 1)[1]
    submissions = await student_learning_store.submissions_for_student(student_id)
    await callback.answer()
    if not submissions:
        await callback.message.answer("У этого ученика пока нет отправленных работ.")
        return
    for submission in submissions[:20]:
        await callback.message.answer(
            f"ДЗ · {submission['lesson_title']}\nОтправлено: {submission['created_at'][:16].replace('T', ' ')}"
        )
        for item in submission["files"]:
            try:
                if item["content_type"].startswith("image/"):
                    await callback.message.answer_photo(FSInputFile(item["path"]), caption=item["name"])
                else:
                    await callback.message.answer_document(FSInputFile(item["path"]), caption=item["name"])
            except (OSError, TelegramBadRequest):
                await callback.message.answer(f"Файл {item['name']} временно недоступен.")


@dp.message(Command("cancel"))
async def cancel_admin_student_flow(message: types.Message):
    admin_student_flows.pop(str(message.from_user.id), None)
    await message.answer("Действие отменено.")


async def _extract_pdf_text(path):
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)[:60_000]
    except Exception:
        return ""


async def _notify_student_new_lesson(student):
    if not student.get("bound"):
        return
    try:
        async with student_learning_store.lock:
            saved = student_learning_store._load()["students"].get(student["id"], {})
        if saved.get("telegram_user_id"):
            await bot.send_message(
                int(saved["telegram_user_id"]),
                "📚 В кабинете ученика появился новый конспект, тест и домашнее задание.",
            )
    except (
        OSError,
        ValueError,
        TelegramBadRequest,
        TelegramForbiddenError,
        TelegramNetworkError,
        TelegramServerError,
    ):
        # The lesson is already saved. A blocked chat must not turn a successful
        # admin action into a false failure report.
        pass


def _render_homework_pdf(path, title, student_name, tasks):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as error:
        raise StudentLearningError("Модуль создания PDF не установлен") from error
    font_path = next((item for item in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ) if os.path.isfile(item)), None)
    if not font_path:
        raise StudentLearningError("На сервере не найден шрифт для русского PDF")
    pdfmetrics.registerFont(TTFont("StudentSans", font_path))
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("StudentNormal", parent=styles["BodyText"], fontName="StudentSans", fontSize=11, leading=16, textColor=colors.HexColor("#15213b"), spaceAfter=6)
    heading = ParagraphStyle("StudentHeading", parent=normal, fontSize=18, leading=23, alignment=TA_CENTER, textColor=colors.HexColor("#263a79"), spaceAfter=12)
    story = [Paragraph(title, heading), Paragraph(f"Ученик: {student_name}", normal), Spacer(1, 5 * mm)]
    for index, task in enumerate(tasks, 1):
        safe_text = str(task).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        story.append(Paragraph(f"<b>{index}.</b> {safe_text}", normal))
        story.append(Spacer(1, 3 * mm))
    document = SimpleDocTemplate(path, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=title)
    document.build(story)


async def _generate_student_package(student, notes_text, next_topic, output_dir, notes_path):
    if not OPENAI_API_KEY:
        raise StudentLearningError("На сервере не настроен OPENAI_API_KEY для генерации теста и ДЗ")
    prompt = (
        f"Класс: {student['grade']}\nГлобальная цель: {student.get('goal', '')}\n"
        f"Особенности ученика: {student.get('facts', '')}\nСледующая тема: {next_topic or 'не указана'}\n\n"
        f"КОНСПЕКТ:\n{notes_text}"
    )
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "next_topic": {"type": "string"},
            "test_questions": {"type": "array", "minItems": 5, "maxItems": 10, "items": {
                "type": "object", "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "string"}},
                    "correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                }, "required": ["question", "options", "correct_index", "explanation"], "additionalProperties": False,
            }},
            "homework_tasks": {"type": "array", "minItems": 5, "maxItems": 12, "items": {"type": "string"}},
        },
        "required": ["title", "next_topic", "test_questions", "homework_tasks"],
        "additionalProperties": False,
    }
    with open(notes_path, "rb") as source:
        encoded_notes = base64.b64encode(source.read()).decode("ascii")
    request_payload = {
        "model": OPENAI_GRADER_MODEL,
        "store": False,
        "instructions": (
            "Ты опытный школьный преподаватель математики. На основе конспекта создай персональный тест и ДЗ. "
            "Тест проверяет понимание теории и ключевых идей, ровно один вариант верный. "
            "Нельзя копировать примеры из конспекта: во всех задачах замени числа, функции, объекты и формулировки, "
            "сохранив проверяемый навык. ДЗ закрепляет прошедший урок и мягко подводит к следующей теме. "
            "Все задания должны соответствовать указанному классу, быть однозначными и математически корректными."
        ),
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_file", "filename": "lesson-notes.pdf", "file_data": f"data:application/pdf;base64,{encoded_notes}"},
        ]}],
        "text": {"format": {"type": "json_schema", "name": "student_lesson_package", "strict": True, "schema": schema}},
    }
    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=request_payload,
        ) as response:
            response_data = await response.json(content_type=None)
            if response.status >= 400:
                raise StudentLearningError("ИИ не смог сформировать комплект урока")
    output_text = response_data.get("output_text")
    if not output_text:
        for item in response_data.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    output_text = part.get("text")
                    break
    try:
        generated = json.loads(output_text or "")
    except json.JSONDecodeError as error:
        raise StudentLearningError("ИИ вернул неполный комплект урока") from error
    homework_path = os.path.join(output_dir, "homework.pdf")
    _render_homework_pdf(homework_path, f"Домашнее задание · {generated['title']}", student["displayName"], generated["homework_tasks"])
    generated["homework_path"] = homework_path
    generated["generation_status"] = "ready"
    return generated


@dp.message()
async def admin_student_flow_message(message: types.Message):
    if not is_admin_telegram_user(message.from_user):
        return
    flow = admin_student_flows.get(str(message.from_user.id))
    if not flow:
        return
    if flow["kind"] == "add_student":
        try:
            fields = parse_admin_student_fields(message.text)
            student, password = await student_learning_store.add_student(
                **fields,
            )
        except StudentLearningError as error:
            await message.answer(f"⚠ {error}")
            return
        admin_student_flows.pop(str(message.from_user.id), None)
        await message.answer(
            f"✅ Кабинет создан для {student['displayName']} (@{student['username']})\n"
            f"Класс: {student['grade']}\nВременный пароль: <code>{password}</code>\n\n"
            "Передайте пароль ученику лично. Бот не хранит его открытым текстом; после первого входа кабинет привяжется к Telegram ID.",
            parse_mode="HTML",
        )
        return
    if flow["kind"] == "edit_student":
        lines = [line.strip() for line in (message.text or "").splitlines()]
        if len(lines) < 6:
            await message.answer("Нужно прислать все 6 строк или отправьте /cancel.")
            return
        try:
            student = await student_learning_store.update_student(
                flow["student_id"], lines[0], lines[1], lines[2], lines[3], lines[4], lines[5]
            )
        except StudentLearningError as error:
            await message.answer(f"⚠ {error}")
            return
        admin_student_flows.pop(str(message.from_user.id), None)
        await message.answer(f"✅ Данные {student['displayName']} обновлены.")
        return
    if flow["kind"] == "lesson_pdf":
        document = message.document
        if not document or document.mime_type != "application/pdf":
            await message.answer("Прикрепите именно PDF-файл конспекта или отправьте /cancel.")
            return
        if document.file_size and document.file_size > MAX_STUDENT_FILE_BYTES:
            await message.answer("PDF должен быть меньше 15 МБ.")
            return
        students = await student_learning_store.list_students()
        student = next((item for item in students if item["id"] == flow["student_id"]), None)
        if not student:
            await message.answer("Ученик больше не найден.")
            admin_student_flows.pop(str(message.from_user.id), None)
            return
        if flow.get("mode") == "manual":
            admin_student_flows[str(message.from_user.id)] = {
                **flow,
                "kind": "lesson_manual_test",
                "notes_file_id": document.file_id,
                "notes_name": document.file_name or "Конспект.pdf",
                "caption": message.caption or "",
            }
            await message.answer(
                "Шаг 1 из 2. Пришлите тест текстом или PDF.\n\n"
                "Формат теста:\n"
                "Тема: Квадратные уравнения\n"
                "Следующая тема: Теорема Виета\n\n"
                "1. Какой вопрос проверяем?\n"
                "А) Первый вариант\n"
                "Б) Второй вариант\n"
                "В) Третий вариант\n"
                "Г) Четвёртый вариант\n"
                "Ответ: Б\n"
                "Пояснение: Почему этот ответ верный\n\n"
                "Важно: PDF должен содержать выделяемый текст, а не только фотографии. "
                "Для каждого вопроса нужны 4 варианта, ответ и пояснение. Отмена: /cancel"
            )
            return
        status = await message.answer("⏳ Читаю конспект и создаю персональные тест и ДЗ…")
        try:
            with tempfile.TemporaryDirectory() as directory:
                notes_path = os.path.join(directory, "notes.pdf")
                await bot.download(document, destination=notes_path)
                notes_text = await _extract_pdf_text(notes_path)
                generated = await _generate_student_package(student, notes_text, message.caption or "", directory, notes_path)
                lesson = await student_learning_store.create_lesson(
                    student["id"], notes_path, document.file_name or "Конспект.pdf", generated
                )
            admin_student_flows.pop(str(message.from_user.id), None)
            await status.edit_text(
                f"✅ Урок «{lesson['title']}» добавлен для {student['displayName']}.\n"
                f"Тест: {len(lesson['test_questions'])} вопросов. ДЗ: {len(lesson['homework_tasks'])} заданий."
            )
            await _notify_student_new_lesson(student)
        except (StudentLearningError, aiohttp.ClientError, asyncio.TimeoutError, OSError) as error:
            await status.edit_text(f"⚠ Не удалось подготовить урок: {error}\nСостояние не потеряно — пришлите PDF ещё раз или /cancel.")
        return
    if flow["kind"] == "lesson_manual_test":
        document = message.document
        if not message.text and not document:
            await message.answer("Пришлите тест текстом или PDF или отправьте /cancel.")
            return
        if document and (
            document.mime_type != "application/pdf"
            and not str(document.file_name or "").casefold().endswith(".pdf")
        ):
            await message.answer("Для теста прикрепите PDF-файл или пришлите текст.")
            return
        if document and document.file_size and document.file_size > MAX_STUDENT_FILE_BYTES:
            await message.answer("PDF с тестом должен быть меньше 15 МБ.")
            return
        try:
            test_text = message.text or ""
            if document:
                with tempfile.TemporaryDirectory() as directory:
                    test_path = os.path.join(directory, "test.pdf")
                    await bot.download(document, destination=test_path)
                    test_text = await _extract_pdf_text(test_path)
                if not test_text.strip():
                    raise StudentLearningError(
                        "В PDF не нашёлся выделяемый текст. "
                        "Пришлите PDF с текстовым слоем или вставьте тест сообщением"
                    )
            fallback_title = os.path.splitext(flow.get("notes_name") or "")[0]
            generated = parse_manual_test_content(test_text, fallback_title=fallback_title)
        except StudentLearningError as error:
            await message.answer(f"⚠ {error}\n\nИсправьте тест и пришлите его ещё раз или отправьте /cancel.")
            return
        admin_student_flows[str(message.from_user.id)] = {
            **flow,
            "kind": "lesson_manual_homework",
            "title": generated["title"],
            "next_topic": generated["next_topic"],
            "test_questions": generated["test_questions"],
        }
        await message.answer(
            f"✅ Тест распознан: {len(generated['test_questions'])} вопросов.\n\n"
            "Шаг 2 из 2. Теперь пришлите ДЗ:\n"
            "• текстом — каждое задание с новой строки;\n"
            "• или готовым PDF-файлом.\n\nОтмена: /cancel"
        )
        return
    if flow["kind"] == "lesson_manual_homework":
        document = message.document
        if not message.text and not document:
            await message.answer("Пришлите ДЗ текстом или PDF или отправьте /cancel.")
            return
        if document and (
            document.mime_type != "application/pdf"
            and not str(document.file_name or "").casefold().endswith(".pdf")
        ):
            await message.answer("Для ДЗ прикрепите PDF-файл или пришлите текст.")
            return
        if document and document.file_size and document.file_size > MAX_STUDENT_FILE_BYTES:
            await message.answer("PDF с ДЗ должен быть меньше 15 МБ.")
            return
        try:
            homework_tasks = [] if document else parse_manual_homework_content(message.text)
        except StudentLearningError as error:
            await message.answer(f"⚠ {error}\n\nИсправьте ДЗ и пришлите его ещё раз или /cancel.")
            return
        students = await student_learning_store.list_students()
        student = next((item for item in students if item["id"] == flow["student_id"]), None)
        if not student:
            await message.answer("Ученик больше не найден.")
            admin_student_flows.pop(str(message.from_user.id), None)
            return
        status = await message.answer("⏳ Сохраняю конспект, тест и ДЗ…")
        try:
            with tempfile.TemporaryDirectory() as directory:
                notes_path = os.path.join(directory, "notes.pdf")
                await bot.download(flow["notes_file_id"], destination=notes_path)
                homework_path = os.path.join(directory, "homework.pdf")
                if document:
                    await bot.download(document, destination=homework_path)
                    extracted_homework = await _extract_pdf_text(homework_path)
                    if extracted_homework.strip():
                        try:
                            homework_tasks = parse_manual_homework_content(extracted_homework)
                        except StudentLearningError:
                            homework_tasks = []
                else:
                    _render_homework_pdf(
                        homework_path,
                        f"Домашнее задание · {flow['title']}",
                        student["displayName"],
                        homework_tasks,
                    )
                generated = {
                    "title": flow["title"],
                    "next_topic": flow.get("next_topic") or flow.get("caption", ""),
                    "test_questions": flow["test_questions"],
                    "homework_tasks": homework_tasks,
                    "homework_path": homework_path,
                    "generation_status": "manual",
                }
                lesson = await student_learning_store.create_lesson(
                    student["id"], notes_path, flow["notes_name"], generated
                )
            admin_student_flows.pop(str(message.from_user.id), None)
            homework_summary = "PDF-файл" if document else f"{len(lesson['homework_tasks'])} заданий"
            await status.edit_text(
                f"✅ Урок «{lesson['title']}» добавлен для {student['displayName']} без OpenAI.\n"
                f"Тест: {len(lesson['test_questions'])} вопросов. "
                f"ДЗ: {homework_summary}.\n"
                "Ежедневные напоминания будут приходить в установленное для ученика время до отправки ДЗ."
            )
            await _notify_student_new_lesson(student)
        except (StudentLearningError, OSError) as error:
            await status.edit_text(
                f"⚠ Не удалось сохранить урок: {error}\n"
                "Текст не потерян: исправьте причину и пришлите его ещё раз или /cancel."
            )

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


async def handle_adventure_script(request):
    return web.FileResponse('adventure.js', headers={"Cache-Control": "no-store, max-age=0"})


async def handle_student_learning_script(request):
    return web.FileResponse('student-learning.js', headers={"Cache-Control": "no-store, max-age=0"})


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
            expert_payload = None
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
            if EXPERT_GAME_FOLDER_ID:
                try:
                    expert_payload = await fetch_expert_game_index(
                        session, EXPERT_GAME_FOLDER_ID
                    )
                except (QuestionFormatError, aiohttp.ClientError, asyncio.TimeoutError):
                    if force:
                        raise

        questions = parse_questions_csv(csv_text)
        # Files 1–5 are the verified legacy set. The Drive parser ignores these
        # numeric-only filenames and adds only new files following "6 - answer".
        if os.path.exists(LOCAL_IMAGE_QUESTIONS_FILE):
            with open(LOCAL_IMAGE_QUESTIONS_FILE, "r", encoding="utf-8") as source:
                questions.extend(parse_questions_csv(source.read()))
        if drive_payload is not None:
            questions.extend(parse_drive_index(drive_payload))
            new_extended = parse_extended_drive_index(drive_payload)
        else:
            new_extended = {grade: [] for grade in SUPPORTED_GRADES}
        if expert_payload is not None:
            expert_report = parse_expert_game_index_report(
                expert_payload, EXPERT_GAME_MAX_SCORE
            )
            new_expert = dict(expert_report["banks"])
            # A draft or temporarily malformed number must not erase its last
            # working version while the administrator is filling the folder.
            for failed_bank in expert_report["failedBanks"]:
                grade = failed_bank["grade"]
                task_number = failed_bank["taskNumber"]
                previous_tasks = (
                    questions_cache.get("expert", {})
                    .get(grade, {})
                    .get(task_number)
                )
                if previous_tasks:
                    new_expert.setdefault(grade, {})[task_number] = previous_tasks
            expert_warnings = expert_report["warnings"]
        else:
            new_expert = {}
            expert_warnings = []
        questions = list({question.question_id: question for question in questions}.values())
        # Publish the newly parsed snapshot only after every required source has
        # been validated, so a failed manual refresh leaves the live bank intact.
        questions_cache["extended"] = new_extended
        questions_cache["expert"] = new_expert
        questions_cache["expert_warnings"] = expert_warnings
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
        user = _authenticated_user(request)
        payload = await request.json()
        if not isinstance(payload, dict) or type(payload.get("isCorrect")) is not bool:
            return web.json_response({"error": "Некорректный результат"}, status=400)
        # The owner is always the signed Telegram user, never an ID supplied by JS.
        grade = int(payload.get("grade") or payload.get("class") or 0)
        data = {
            "user_id": user["id"], "username": user.get("username"),
            "questionId": str(payload.get("questionId") or "")[:200],
            "attemptKey": str(payload.get("attemptKey") or "")[:200],
            "grade": grade, "class": grade,
            "topic": str(payload.get("topic") or "Общее")[:300],
            "isCorrect": payload["isCorrect"],
            "time": datetime.now(timezone.utc).isoformat(),
        }
        await community_store.record_attempt(user, data)
        descriptor = os.open(RESULTS_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        return web.json_response({"status": "success"})
    except CommunityError as error:
        return _community_error(error, status=401)
    except (ValueError, TypeError):
        return web.json_response({"error": "Некорректный результат"}, status=400)
    except OSError:
        return web.json_response({"error": "Не удалось сохранить результат. Повторите позже"}, status=500)


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


async def get_daily_login(request):
    try:
        return web.json_response(await community_store.daily_login_status(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=401)


async def spin_daily_wheel(request):
    try:
        return web.json_response(await community_store.spin_daily_wheel(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=422)


async def get_shop(request):
    try:
        return web.json_response(await community_store.shop_catalog(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=401)


async def purchase_shop_item(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        result = await community_store.purchase_shop_item(user, str(payload.get("itemId") or ""))
        purchased_item = result.get("purchasedItem") or {}
        if purchased_item.get("slot") == "guide" and ADMIN_ID:
            profile = await community_store.get_profile(user)
            telegram_username = str(user.get("username") or "").strip().lstrip("@")
            buyer_contact = f"@{telegram_username}" if telegram_username else f"Telegram ID {user.get('id')}"
            try:
                await bot.send_message(
                    int(ADMIN_ID),
                    "📚 Куплен учебный материал\n"
                    f"Покупатель: {buyer_contact}\n"
                    f"Ник в приложении: {profile.get('nickname', 'Участник')}\n"
                    f"Материал: {purchased_item.get('name', 'Без названия')}\n"
                    f"Списано: {result.get('paid', 0)} монет\n"
                    f"Файл кабинета: /data/materials/{purchased_item.get('id', '')}.pdf\n"
                    "Нужно добавить соответствующий PDF в хранилище. Покупатель откроет его в личном кабинете.",
                )
            except (
                TelegramBadRequest,
                TelegramForbiddenError,
                TelegramNetworkError,
                TelegramRetryAfter,
                TelegramServerError,
                ValueError,
            ):
                # Покупка уже сохранена: недоступность служебного уведомления
                # не должна отнимать материал или повторно списывать монеты.
                pass
        return web.json_response(result)
    except CommunityError as error:
        return _community_error(error, status=422)


async def equip_shop_item(request):
    try:
        payload = await request.json()
        return web.json_response(await community_store.equip_shop_item(
            _authenticated_user(request),
            str(payload.get("itemId") or ""),
            bool(payload.get("remove")),
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


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
        return web.json_response(
            await community_store.character_catalog(_authenticated_user(request)),
            headers={"Cache-Control": "no-store, max-age=0"},
        )
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


async def get_material_file(request):
    try:
        material = await community_store.material_access(
            _authenticated_user(request), request.match_info.get("item_id", "")
        )
        return web.FileResponse(
            material["path"],
            headers={
                "Cache-Control": "private, no-store, max-age=0",
                "Content-Disposition": "inline",
            },
        )
    except CommunityError as error:
        return _community_error(error, status=404)


async def get_leaderboard(request):
    try:
        user = _authenticated_user(request)
        grade_value = request.query.get("grade")
        grade = int(grade_value) if grade_value else None
        return web.json_response(
            await community_store.leaderboard(request.query.get("period", "day"), grade, str(user["id"]))
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


async def get_blocks(request):
    return web.json_response(await community_store.blocked_participants(_authenticated_user(request)))


async def change_block(request):
    try:
        return web.json_response(await community_store.block_participant(
            _authenticated_user(request), request.match_info["public_id"],
            remove=request.method == "DELETE",
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


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


async def get_active_battle(request):
    try:
        return web.json_response(
            await community_store.active_battle(_authenticated_user(request))
        )
    except CommunityError as error:
        return _community_error(error, status=401)


async def forfeit_battle(request):
    try:
        questions = await _load_questions()
        question_map = {question.question_id: question for question in questions}
        return web.json_response(await community_store.forfeit_battle(
            _authenticated_user(request), request.match_info["battle_id"], question_map
        ))
    except CommunityError as error:
        return _community_error(error, status=422)
    except (QuestionFormatError, aiohttp.ClientError, asyncio.TimeoutError) as error:
        return _community_error(error, status=502)


async def get_battle_stats(request):
    try:
        return web.json_response(await community_store.battle_stats(_authenticated_user(request)))
    except CommunityError as error:
        return _community_error(error, status=401)


async def spin_battle_reward(request):
    try:
        payload = await request.json()
        return web.json_response(await community_store.spin_battle_reward(
            _authenticated_user(request), str(payload.get("tier") or "")
        ))
    except (CommunityError, ValueError, TypeError) as error:
        return _community_error(error, status=422)


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
    try:
        user = _authenticated_user(request)
    except CommunityError as error:
        return _community_error(error, status=401)
    user_id = str(user["id"])
    if request.query.get("user_id") not in (None, "", user_id):
        return web.json_response({"error": "Доступна только ваша статистика"}, status=403)
    
    stats = {"total": 0, "correct": 0, "topics": {}}
    
    # Если файла еще нет, просто возвращаем нули (0%)
    if not os.path.exists(RESULTS_FILE):
        return web.json_response(stats)
        
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if str(data.get('user_id')) == user_id:
                        stats["total"] += 1
                        if data.get('isCorrect'):
                            stats["correct"] += 1
                        
                        topic = normalise_stats_topic(data.get('topic', 'Общее'))
                        if topic not in stats["topics"]:
                            stats["topics"][topic] = {"total": 0, "correct": 0}
                        stats["topics"][topic]["total"] += 1
                        if data.get('isCorrect'):
                            stats["topics"][topic]["correct"] += 1
                except: continue
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
                
    return web.json_response(stats)


def normalise_stats_topic(value):
    topic = " ".join(str(value or "").split()).strip(" .,:;-")
    if not topic:
        return "Общее"
    lower = topic.casefold().replace("ё", "е")
    looks_like_task = (
        len(topic) > 72
        or "?" in topic
        or sum(char.isdigit() for char in topic) >= 3
        or ("=" in topic and len(topic.split()) >= 5)
        or len(topic.split()) > 10
    )
    if not looks_like_task:
        return topic[:72]
    groups = (
        ("Геометрия", ("треуг", "окруж", "угол", "площад", "радиус", "сторон", "прямоуг", "вектор")),
        ("Тригонометрия", ("sin", "cos", "tg", "ctg", "синус", "косин", "танген")),
        ("Логарифмы", ("log", "логариф")),
        ("Функции и производная", ("функц", "график", "производн", "касатель")),
        ("Уравнения и неравенства", ("уравнен", "неравен", "корн", "дискриминант")),
        ("Вероятность и статистика", ("вероят", "средн", "медиан", "событ")),
        ("Проценты и текстовые задачи", ("процент", "скорост", "вклад", "стоимост", "мощност", "температур")),
    )
    for label, markers in groups:
        if any(marker in lower for marker in markers):
            return label
    return "Смешанные задачи"


async def get_training_history(request):
    try:
        user = _authenticated_user(request)
        grade_value = request.query.get("grade")
        grade = int(grade_value) if grade_value else None
        grouped = {}
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, "r", encoding="utf-8") as source:
                for line in source:
                    try:
                        item = json.loads(line)
                        if str(item.get("user_id")) != str(user["id"]):
                            continue
                        item_grade = int(item.get("grade") or item.get("class") or 0)
                        if grade and item_grade != grade:
                            continue
                        key = str(item.get("attemptKey") or item.get("time") or "legacy")
                        row = grouped.setdefault(key, {
                            "id": key,
                            "grade": item_grade,
                            "createdAt": item.get("time"),
                            "total": 0,
                            "correct": 0,
                            "topics": set(),
                        })
                        row["total"] += 1
                        row["correct"] += int(bool(item.get("isCorrect")))
                        row["topics"].add(normalise_stats_topic(item.get("topic")))
                        if item.get("time") and (not row["createdAt"] or item["time"] > row["createdAt"]):
                            row["createdAt"] = item["time"]
                    except (ValueError, TypeError, json.JSONDecodeError):
                        continue
        entries = sorted(grouped.values(), key=lambda item: item.get("createdAt") or "", reverse=True)[:30]
        for entry in entries:
            entry["topics"] = sorted(entry["topics"])
            entry["percent"] = round(entry["correct"] * 100 / entry["total"]) if entry["total"] else 0
        extended_entries = await community_store.adventure_history(user, grade)
        for entry in extended_entries:
            entry["percent"] = round(entry["correct"] * 100 / entry["total"]) if entry["total"] else 0
        entries = sorted(
            entries + extended_entries,
            key=lambda item: item.get("createdAt") or "",
            reverse=True,
        )[:30]
        return web.json_response({"entries": entries})
    except CommunityError as error:
        return _community_error(error, status=401)


async def get_adventure(request):
    try:
        payload = await community_store.get_adventure(
            _authenticated_user(request), int(request.query.get("grade") or 0)
        )
        if payload.get("active"):
            payload["session"]["verification"] = _adventure_verification_capabilities()
        return web.json_response(payload)
    except (CommunityError, TypeError, ValueError) as error:
        return _community_error(error, status=422)


async def get_expert_banks(request):
    try:
        _authenticated_user(request)
        grade = int(request.query.get("grade") or 0)
        if grade not in SUPPORTED_GRADES:
            raise CommunityError("Выберите класс от 8 до 11")
        await _load_questions()
        banks = questions_cache.get("expert", {}).get(grade, {})
        return web.json_response({
            "grade": grade,
            "numbers": [
                {
                    "number": number,
                    "count": len(banks.get(number, [])),
                    "active": number == 13 and bool(banks.get(number)),
                }
                for number in range(13, 20)
            ],
        })
    except (CommunityError, TypeError, ValueError) as error:
        return _community_error(error, status=422)


async def start_adventure(request):
    try:
        payload = await request.json()
        grade = int(payload.get("grade") or 0)
        game = str(payload.get("game") or "tower")
        user = _authenticated_user(request)
        attempt_key = str(payload.get("attemptKey") or "").strip()
        task = None
        if game in {"second_part", "expert"}:
            await _load_questions()
            if game == "expert":
                task_number = int(payload.get("taskNumber") or 13)
                if task_number != 13:
                    raise CommunityError(f"Задание {task_number} пока находится в разработке")
                available = (
                    questions_cache.get("expert", {})
                    .get(grade, {})
                    .get(task_number, [])
                )
            else:
                available = questions_cache.get("extended", {}).get(grade, [])
            used_ids = await community_store.used_adventure_task_ids(user, grade, attempt_key)
            fresh_tasks = [task for task in available if task.get("id") not in used_ids]
            # Once every task in the folder has been solved, a new shuffled cycle may begin.
            if game == "expert":
                task = fresh_tasks or available
            else:
                task = random.choice(fresh_tasks or available) if available else None
            if game == "expert" and not task:
                raise CommunityError("В папке игры пока нет готовых комплектов «Решение — Ответ — Критерии»")
        session = await community_store.start_adventure(
            user, grade, attempt_key, task=task, game=game
        )
        session["verification"] = _adventure_verification_capabilities()
        return web.json_response(session)
    except (CommunityError, TypeError, ValueError) as error:
        return _community_error(error, status=422)


def _adventure_verification_capabilities():
    return {
        "structuredCheck": True,
        "expertCheck": bool(OPENAI_API_KEY),
        "photoRecognition": bool(MATHPIX_APP_ID and MATHPIX_APP_KEY),
    }


async def answer_adventure_formula(request):
    try:
        payload = await request.json()
        session = await community_store.answer_adventure_formula(
            _authenticated_user(request), request.match_info["session_id"], payload.get("optionId")
        )
        session["verification"] = _adventure_verification_capabilities()
        return web.json_response(session)
    except CommunityError as error:
        return _community_error(error, status=422)


async def leave_adventure(request):
    try:
        session = await community_store.leave_adventure(
            _authenticated_user(request), request.match_info["session_id"]
        )
        session["verification"] = _adventure_verification_capabilities()
        return web.json_response(session)
    except CommunityError as error:
        return _community_error(error, status=422)


async def save_adventure_draft(request):
    try:
        payload = await request.json()
        return web.json_response(await community_store.save_adventure_draft(
            _authenticated_user(request), request.match_info["session_id"], payload
        ))
    except CommunityError as error:
        return _community_error(error, status=422)


async def submit_adventure(request):
    try:
        user = _authenticated_user(request)
        payload = await request.json()
        context = await community_store.adventure_context(user, request.match_info["session_id"])
        expert_result = await _grade_extended_solution(context, payload)
        session = await community_store.submit_adventure(
            user, request.match_info["session_id"], payload, expert_result=expert_result
        )
        session["verification"] = _adventure_verification_capabilities()
        return web.json_response(session)
    except CommunityError as error:
        return _community_error(error, status=422)


async def submit_expert_score(request):
    try:
        payload = await request.json()
        session = await community_store.submit_expert_score(
            _authenticated_user(request),
            request.match_info["session_id"],
            payload.get("score"),
        )
        session["verification"] = _adventure_verification_capabilities()
        return web.json_response(session)
    except CommunityError as error:
        return _community_error(error, status=422)


async def continue_expert_game(request):
    try:
        session = await community_store.continue_expert_game(
            _authenticated_user(request), request.match_info["session_id"]
        )
        session["verification"] = _adventure_verification_capabilities()
        return web.json_response(session)
    except CommunityError as error:
        return _community_error(error, status=422)


async def _grade_extended_solution(context, payload):
    if not OPENAI_API_KEY:
        return None
    task = context["task"]
    grade = int(context["grade"])
    reference = {
        field["label"]: field.get("answers", [])
        for field in task.get("fields", [])
    }
    criteria = (
        "ОГЭ: 2 — математически грамотное завершённое решение с понятным ходом; "
        "1 — верный ход с несущественной или вычислительной ошибкой либо незавершённостью; "
        "0 — только ответ, фрагменты или существенная математическая ошибка."
        if grade == 9 else
        "ЕГЭ: применяй критерии указанного типа задания; проверяй ограничения, корректность преобразований, полноту обоснований и ответ."
        if grade == 11 else
        "Проверяй как учитель математики: корректность каждого преобразования, полноту обоснований и совпадение ответа. Шкала 0–2."
    )
    text = (
        f"Класс: {grade}\nТип: {task.get('kind')}\nУсловие: {task.get('question')}\n"
        f"Эталонные ответы: {json.dumps(reference, ensure_ascii=False)}\nКритерии: {criteria}\n"
        f"Поля ученика: {json.dumps(payload.get('answers') or {}, ensure_ascii=False)}\n"
        f"Распознанный/введённый ход решения: {str(payload.get('explanation') or '')[:5000]}"
    )
    content = [{"type": "input_text", "text": text}]
    for image_value in (task.get("imageUrl"), payload.get("conditionImage"), payload.get("solutionImage")):
        if image_value:
            content.append({"type": "input_image", "image_url": image_value, "detail": "high"})
    request_payload = {
        "model": OPENAI_GRADER_MODEL,
        "store": False,
        "instructions": (
            "Ты строгий, но объективный эксперт по школьной математике. Оцени только представленное решение. "
            "Не требуй конкретного оформления, если ход математически верен. Не выдавай полный балл за один ответ без решения. "
            "Если символ неразборчив, перечисли его в uncertainSymbols и не угадывай."
        ),
        "input": [{"role": "user", "content": content}],
        "text": {"format": {
            "type": "json_schema",
            "name": "math_solution_grade",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 2},
                    "verdict": {"type": "string"},
                    "criteria": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "correct": {"type": "boolean"},
                            "earned": {"type": "integer", "minimum": 0, "maximum": 2},
                            "max": {"type": "integer", "minimum": 0, "maximum": 2},
                        },
                        "required": ["label", "correct", "earned", "max"],
                        "additionalProperties": False,
                    }},
                    "uncertainSymbols": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["score", "verdict", "criteria", "uncertainSymbols"],
                "additionalProperties": False,
            },
        }},
    }
    try:
        timeout = aiohttp.ClientTimeout(total=50)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json=request_payload,
            ) as response:
                response_data = await response.json(content_type=None)
                if response.status >= 400:
                    return None
        output_text = response_data.get("output_text")
        if not output_text:
            for item in response_data.get("output", []):
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        output_text = part.get("text")
                        break
        result = json.loads(output_text or "")
        result["maxScore"] = 2
        if result.get("uncertainSymbols"):
            result["verdict"] += " Уточните символы через MathLive: " + ", ".join(result["uncertainSymbols"][:5])
        return result
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError, json.JSONDecodeError):
        return None


async def recognize_solution(request):
    try:
        _authenticated_user(request)
        payload = await request.json()
        image_data = str(payload.get("image") or "")
        if not image_data.startswith("data:image/") or len(image_data) > 1_000_000:
            raise CommunityError("Фото для распознавания отсутствует или слишком велико")
        if not MATHPIX_APP_ID or not MATHPIX_APP_KEY:
            return web.json_response({
                "configured": False,
                "message": "Фото сохранено. Автопроверка введённых ответов работает; неясные символы уточните через математическую клавиатуру.",
            })
        timeout = aiohttp.ClientTimeout(total=35)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.mathpix.com/v3/text",
                headers={
                    "app_id": MATHPIX_APP_ID,
                    "app_key": MATHPIX_APP_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "src": image_data,
                    "formats": ["text"],
                    "math_inline_delimiters": ["$", "$"],
                    "rm_spaces": False,
                },
            ) as response:
                result = await response.json(content_type=None)
                if response.status >= 400:
                    raise CommunityError("Сервис не смог распознать фотографию")
        confidence = float(result.get("confidence") or result.get("confidence_rate") or 0)
        return web.json_response({
            "configured": True,
            "text": str(result.get("text") or "")[:6000],
            "confidence": confidence,
            "needsConfirmation": confidence < 0.82,
        })
    except CommunityError as error:
        return _community_error(error, status=422)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError):
        return _community_error(CommunityError("Распознавание временно недоступно"), status=502)


def _student_error(error, status=422):
    return web.json_response({"error": str(error)}, status=status)


async def get_student_status(request):
    try:
        return web.json_response(await student_learning_store.status(_authenticated_user(request)))
    except StudentLearningError as error:
        return _student_error(error)


async def login_student(request):
    try:
        payload = await request.json()
        student = await student_learning_store.login(
            _authenticated_user(request), payload.get("password"), payload.get("reminderTime")
        )
        return web.json_response({"authenticated": True, "student": student})
    except (StudentLearningError, ValueError, TypeError, json.JSONDecodeError) as error:
        return _student_error(error)


async def get_student_dashboard(request):
    try:
        return web.json_response(await student_learning_store.dashboard(_authenticated_user(request)))
    except StudentLearningError as error:
        return _student_error(error, status=403)


async def open_student_lesson(request):
    try:
        return web.json_response(await student_learning_store.open_lesson(
            _authenticated_user(request), request.match_info["lesson_id"]
        ))
    except StudentLearningError as error:
        return _student_error(error, status=403)


async def confirm_student_lesson(request):
    try:
        return web.json_response(await student_learning_store.confirm_reading(
            _authenticated_user(request), request.match_info["lesson_id"]
        ))
    except StudentLearningError as error:
        return _student_error(error, status=403)


async def get_student_material(request):
    try:
        path, lesson = await student_learning_store.material_path(
            _authenticated_user(request), request.match_info["lesson_id"], request.match_info["kind"]
        )
        filename = "Конспект.pdf" if request.match_info["kind"] == "notes" else "Домашнее задание.pdf"
        return web.FileResponse(
            path,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{urlencode({'x': filename})[2:]}",
                "Content-Type": "application/pdf",
                "X-Lesson-Title": str(lesson.get("title") or "")[:120],
            },
        )
    except StudentLearningError as error:
        return _student_error(error, status=404)


async def get_student_test(request):
    try:
        return web.json_response(await student_learning_store.test(
            _authenticated_user(request), request.match_info["lesson_id"]
        ))
    except StudentLearningError as error:
        return _student_error(error, status=403)


async def check_student_test_answer(request):
    try:
        payload = await request.json()
        return web.json_response(await student_learning_store.check_test_answer(
            _authenticated_user(request),
            request.match_info["lesson_id"],
            payload.get("questionIndex"),
            payload.get("answer"),
        ))
    except (StudentLearningError, ValueError, TypeError, json.JSONDecodeError) as error:
        return _student_error(error)


async def submit_student_test(request):
    try:
        payload = await request.json()
        return web.json_response(await student_learning_store.submit_test(
            _authenticated_user(request), request.match_info["lesson_id"], payload.get("answers")
        ))
    except (StudentLearningError, ValueError, TypeError, json.JSONDecodeError) as error:
        return _student_error(error)


def _admin_chat_ids():
    result = []
    if ADMIN_ID:
        try:
            result.append(int(ADMIN_ID))
        except ValueError:
            pass
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as source:
                users = json.load(source)
            if isinstance(users, dict):
                for user_id, record in users.items():
                    username = str((record or {}).get("username") or "").casefold()
                    if username == "supertutor15":
                        result.append(int(user_id))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return list(dict.fromkeys(result))


async def submit_student_homework(request):
    try:
        user = _authenticated_user(request)
        reader = await request.multipart()
        lesson_id = ""
        uploads = []
        async for part in reader:
            if part.name == "lessonId":
                lesson_id = (await part.text()).strip()
                continue
            if part.name != "files":
                continue
            content_type = str(part.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            if content_type not in ALLOWED_STUDENT_FILE_TYPES:
                raise StudentLearningError("Разрешены PDF, JPG, PNG и WebP")
            data = await part.read(decode=False)
            if len(data) > MAX_STUDENT_FILE_BYTES:
                raise StudentLearningError("Каждый файл должен быть меньше 15 МБ")
            uploads.append({"name": part.filename, "content_type": content_type, "data": data})
            if len(uploads) > 50:
                raise StudentLearningError("Отправляйте не более 50 файлов за один раз; следующую часть можно отправить отдельно")
        result = await student_learning_store.save_submission(user, lesson_id, uploads)
        username = str(user.get("username") or "").lstrip("@")
        notice = (
            f"📥 {result['student']['displayName']} (@{username or result['student']['username']}) прикрепил(а) ДЗ\n"
            f"Урок: {result['lessonTitle']}\nФайлов: {result['files']}\n\n"
            "Открыть: /admin → «Проверить ДЗ»"
        )
        for chat_id in _admin_chat_ids():
            try:
                await bot.send_message(chat_id, notice)
            except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramServerError):
                pass
        return web.json_response(result)
    except StudentLearningError as error:
        return _student_error(error)
    except (ValueError, TypeError, OSError) as error:
        return _student_error(StudentLearningError("Не удалось сохранить файлы ДЗ"))
def security_middleware():
    # Bounded, per-worker limits. Persistent friendship limits also survive restarts.
    windows = OrderedDict()

    def allowed(key, limit):
        now = time.monotonic()
        events = windows.setdefault(key, deque())
        windows.move_to_end(key)
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        while len(windows) > 10000:
            windows.popitem(last=False)
        return True

    @web.middleware
    async def middleware(request, handler):
        private = request.path in {"/save", "/stats"} or (
            request.path.startswith("/api/") and request.path != "/api/questions"
        )
        try:
            if private:
                user = _authenticated_user(request)
                category = "search" if request.path == "/api/participants/search" else "general"
                if (not allowed((user["id"], "all"), 240)
                        or (category == "search" and not allowed((user["id"], category), 20))):
                    response = web.json_response({"error": "Слишком много запросов. Подождите минуту"}, status=429,
                                                 headers={"Retry-After": "60"})
                else:
                    response = await handler(request)
            else:
                response = await handler(request)
        except CommunityError as error:
            response = _community_error(error, status=401)
        except web.HTTPException as error:
            response = web.Response(status=error.status, text=error.text, headers=error.headers)
        if private:
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            response.headers["Vary"] = "X-Telegram-Init-Data"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return middleware


def create_app():
    application = web.Application(client_max_size=64 * 1024 * 1024, middlewares=[security_middleware()])
    application.router.add_get('/', handle_index)
    application.router.add_get('/app.css', handle_styles)
    application.router.add_get('/community.js', handle_community_script)
    application.router.add_get('/characters.js', handle_character_script)
    application.router.add_get('/math-format.js', handle_math_script)
    application.router.add_get('/adventure.js', handle_adventure_script)
    application.router.add_get('/student-learning.js', handle_student_learning_script)
    application.router.add_static('/assets/', 'assets', show_index=False)
    application.router.add_get('/api/questions', get_questions)
    application.router.add_post('/save', save_progress)
    application.router.add_get('/stats', get_stats)
    application.router.add_get('/api/training-history', get_training_history)
    application.router.add_get('/api/adventure', get_adventure)
    application.router.add_get('/api/adventure/expert-banks', get_expert_banks)
    application.router.add_post('/api/adventure/start', start_adventure)
    application.router.add_post('/api/adventure/{session_id}/formula', answer_adventure_formula)
    application.router.add_post('/api/adventure/{session_id}/leave', leave_adventure)
    application.router.add_post('/api/adventure/{session_id}/draft', save_adventure_draft)
    application.router.add_post('/api/adventure/{session_id}/submit', submit_adventure)
    application.router.add_post('/api/adventure/{session_id}/expert-score', submit_expert_score)
    application.router.add_post('/api/adventure/{session_id}/expert-next', continue_expert_game)
    application.router.add_post('/api/adventure/recognize', recognize_solution)
    application.router.add_get('/api/profile', get_profile)
    application.router.add_post('/api/profile', update_profile)
    application.router.add_post('/api/daily-login', claim_daily_login)
    application.router.add_get('/api/daily-login', get_daily_login)
    application.router.add_post('/api/daily-wheel', spin_daily_wheel)
    application.router.add_get('/api/shop', get_shop)
    application.router.add_post('/api/shop/purchase', purchase_shop_item)
    application.router.add_post('/api/shop/equip', equip_shop_item)
    application.router.add_post('/api/coins/training', award_training_coins)
    application.router.add_get('/api/characters', get_characters)
    application.router.add_post('/api/characters/select', select_character)
    application.router.add_post('/api/characters/purchase', purchase_character)
    application.router.add_get('/avatars/{filename}', get_avatar)
    application.router.add_get('/api/materials/{item_id}', get_material_file)
    application.router.add_get('/api/leaderboard', get_leaderboard)
    application.router.add_get('/api/participants/search', search_participants)
    application.router.add_get('/api/participants/{public_id}', get_participant)
    application.router.add_get('/api/friends', get_friends)
    application.router.add_get('/api/blocks', get_blocks)
    application.router.add_post('/api/blocks/{public_id}', change_block)
    application.router.add_delete('/api/blocks/{public_id}', change_block)
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
    application.router.add_get('/api/battles/active', get_active_battle)
    application.router.add_get('/api/battle-stats', get_battle_stats)
    application.router.add_post('/api/battle-rewards/spin', spin_battle_reward)
    application.router.add_get('/api/battles/{battle_id}', get_battle)
    application.router.add_post('/api/battles/{battle_id}/forfeit', forfeit_battle)
    application.router.add_post('/api/battles/{battle_id}/answer', answer_battle)
    application.router.add_get('/api/student/status', get_student_status)
    application.router.add_post('/api/student/login', login_student)
    application.router.add_get('/api/student/dashboard', get_student_dashboard)
    application.router.add_post('/api/student/lessons/{lesson_id}/open', open_student_lesson)
    application.router.add_post('/api/student/lessons/{lesson_id}/read', confirm_student_lesson)
    application.router.add_get('/api/student/lessons/{lesson_id}/{kind:notes|homework}', get_student_material)
    application.router.add_get('/api/student/lessons/{lesson_id}/test', get_student_test)
    application.router.add_post('/api/student/lessons/{lesson_id}/test/check', check_student_test_answer)
    application.router.add_post('/api/student/lessons/{lesson_id}/test', submit_student_test)
    application.router.add_post('/api/student/homework', submit_student_homework)
    return application


app = create_app()


# === ЗАПУСК ===

async def student_reminder_worker():
    while True:
        try:
            for reminder in await student_learning_store.reminder_candidates():
                try:
                    await bot.send_message(
                        reminder["telegram_user_id"],
                        f"⏰ Напоминание о домашнем задании к уроку «{reminder['lesson_title']}». "
                        "Откройте мини-приложение → «Кабинет ученика» → «ДЗ»."
                    )
                except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramServerError):
                    pass
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        await asyncio.sleep(30)

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
    asyncio.create_task(student_reminder_worker())
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    print(f"Сервер запущен на порту {PORT}")
    await site.start()
    while True: 
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
