import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")
SUPPORTED_GRADES = {8, 9, 10, 11}
MAX_STUDENT_FILE_BYTES = 15 * 1024 * 1024
ALLOWED_STUDENT_FILE_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class StudentLearningError(ValueError):
    pass


def _now():
    return datetime.now(MOSCOW)


def _now_iso():
    return _now().isoformat()


def normalize_username(value):
    username = str(value or "").strip().lstrip("@").casefold()
    if not re.fullmatch(r"[a-z0-9_]{5,32}", username):
        raise StudentLearningError("Укажите корректный Telegram username")
    return username


def hash_password(password, salt=None):
    value = str(password or "")
    if len(value) < 8 or len(value) > 128:
        raise StudentLearningError("Пароль должен содержать от 8 до 128 символов")
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt_bytes, 240_000)
    return salt_bytes.hex(), digest.hex()


def verify_password(password, salt, expected):
    try:
        _, actual = hash_password(password, salt)
    except (StudentLearningError, ValueError):
        return False
    return hmac.compare_digest(actual, str(expected or ""))


def generate_temporary_password():
    # Avoid visually ambiguous characters; the password is only shown once to the admin.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _default_data():
    return {"version": 1, "students": {}, "lessons": {}, "submissions": {}}


class StudentLearningStore:
    def __init__(self, path, files_directory=None):
        self.path = path
        self.files_directory = files_directory or os.path.join(
            os.path.dirname(path) or ".", "student_learning"
        )
        self.lock = asyncio.Lock()

    def _load(self):
        if not os.path.exists(self.path):
            return _default_data()
        with open(self.path, "r", encoding="utf-8") as source:
            data = json.load(source)
        default = _default_data()
        for key, value in default.items():
            data.setdefault(key, value)
        data["version"] = default["version"]
        return data

    def _save(self, data):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        temporary = f"{self.path}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(data, target, ensure_ascii=False, indent=2)
        os.replace(temporary, self.path)

    @staticmethod
    def _public_student(student):
        return {
            "id": student["id"],
            "username": student["username"],
            "displayName": student.get("display_name") or f"@{student['username']}",
            "grade": student["grade"],
            "goal": student.get("goal", ""),
            "facts": student.get("facts", ""),
            "lessonSchedule": student.get("lesson_schedule", ""),
            "reminderTime": student.get("reminder_time"),
            "bound": bool(student.get("telegram_user_id")),
            "active": bool(student.get("active", True)),
        }

    @staticmethod
    def _find_student(data, user):
        user_id = str(user.get("id") or "")
        username = str(user.get("username") or "").strip().lstrip("@").casefold()
        for student in data["students"].values():
            if student.get("telegram_user_id") == user_id:
                return student
        for student in data["students"].values():
            if not student.get("telegram_user_id") and username and student.get("username") == username:
                return student
        return None

    @staticmethod
    def _require_bound_student(data, user):
        user_id = str(user.get("id") or "")
        for student in data["students"].values():
            if student.get("telegram_user_id") == user_id and student.get("active", True):
                return student
        raise StudentLearningError("Сначала войдите в режим ученика")

    async def add_student(self, username, grade, goal, facts, lesson_schedule,
                          reminder_time=None, display_name=None, password=None):
        username = normalize_username(username)
        try:
            grade = int(grade)
        except (TypeError, ValueError):
            raise StudentLearningError("Класс должен быть от 8 до 11")
        if grade not in SUPPORTED_GRADES:
            raise StudentLearningError("Класс должен быть от 8 до 11")
        password = password or generate_temporary_password()
        salt, password_hash = hash_password(password)
        async with self.lock:
            data = self._load()
            if any(item.get("username") == username for item in data["students"].values()):
                raise StudentLearningError("Ученик с таким username уже добавлен")
            student_id = uuid.uuid4().hex[:16]
            data["students"][student_id] = {
                "id": student_id,
                "username": username,
                "display_name": str(display_name or "").strip()[:80],
                "grade": grade,
                "goal": str(goal or "").strip()[:4000],
                "facts": str(facts or "").strip()[:6000],
                "lesson_schedule": str(lesson_schedule or "").strip()[:1000],
                "reminder_time": str(reminder_time or "").strip() or None,
                "password_salt": salt,
                "password_hash": password_hash,
                "telegram_user_id": None,
                "active": True,
                "created_at": _now_iso(),
            }
            self._save(data)
            return self._public_student(data["students"][student_id]), password

    async def list_students(self):
        async with self.lock:
            data = self._load()
            return [self._public_student(item) for item in sorted(
                data["students"].values(), key=lambda value: (value["grade"], value["username"])
            )]

    async def update_student(self, student_id, grade, display_name, goal, facts,
                             lesson_schedule, reminder_time):
        try:
            grade = int(grade)
        except (TypeError, ValueError):
            raise StudentLearningError("Класс должен быть от 8 до 11")
        if grade not in SUPPORTED_GRADES:
            raise StudentLearningError("Класс должен быть от 8 до 11")
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(reminder_time or "")):
            raise StudentLearningError("Время напоминания должно быть в формате ЧЧ:ММ")
        async with self.lock:
            data = self._load()
            student = data["students"].get(str(student_id))
            if not student:
                raise StudentLearningError("Ученик не найден")
            student.update({
                "grade": grade,
                "display_name": str(display_name or "").strip()[:80],
                "goal": str(goal or "").strip()[:4000],
                "facts": str(facts or "").strip()[:6000],
                "lesson_schedule": str(lesson_schedule or "").strip()[:1000],
                "reminder_time": str(reminder_time),
                "updated_at": _now_iso(),
            })
            self._save(data)
            return self._public_student(student)

    async def status(self, user):
        async with self.lock:
            data = self._load()
            student = self._find_student(data, user)
            if not student or not student.get("active", True):
                return {"available": False, "authenticated": False}
            bound = student.get("telegram_user_id") == str(user.get("id"))
            return {
                "available": True,
                "authenticated": bound,
                "student": self._public_student(student) if bound else None,
            }

    async def login(self, user, password, reminder_time=None):
        async with self.lock:
            data = self._load()
            student = self._find_student(data, user)
            if not student or not student.get("active", True):
                raise StudentLearningError("Для этого Telegram-аккаунта ученический режим не настроен")
            user_id = str(user.get("id") or "")
            bound_id = student.get("telegram_user_id")
            if bound_id and bound_id != user_id:
                raise StudentLearningError("Кабинет уже привязан к другому Telegram-аккаунту")
            if not verify_password(password, student["password_salt"], student["password_hash"]):
                raise StudentLearningError("Неверный пароль")
            if not bound_id:
                actual_username = str(user.get("username") or "").strip().lstrip("@").casefold()
                if actual_username != student["username"]:
                    raise StudentLearningError("Войдите с Telegram-аккаунта, добавленного преподавателем")
                student["telegram_user_id"] = user_id
                student["bound_at"] = _now_iso()
            if reminder_time:
                if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(reminder_time)):
                    raise StudentLearningError("Время напоминания должно быть в формате ЧЧ:ММ")
                student["reminder_time"] = str(reminder_time)
            self._save(data)
            return self._public_student(student)

    def _latest_lesson(self, data, student_id):
        lessons = [item for item in data["lessons"].values() if item["student_id"] == student_id]
        return max(lessons, key=lambda item: item.get("created_at", ""), default=None)

    def _dashboard_payload(self, data, student):
        lesson = self._latest_lesson(data, student["id"])
        lesson_payload = None
        if lesson:
            opened_at = lesson.get("opened_by_student_at")
            time_unlocked = False
            if opened_at:
                try:
                    time_unlocked = _now() >= datetime.fromisoformat(opened_at) + timedelta(minutes=10)
                except ValueError:
                    pass
            lesson_payload = {
                "id": lesson["id"],
                "title": lesson.get("title") or "Прошедший урок",
                "createdAt": lesson["created_at"],
                "hasNotes": bool(lesson.get("notes_path")),
                "hasHomework": bool(lesson.get("homework_path")),
                "testReady": bool(lesson.get("test_questions")),
                "testUnlocked": bool(lesson.get("reading_confirmed_at")) or time_unlocked,
                "testCompleted": bool(lesson.get("test_completed_at")),
                "testScore": lesson.get("test_score"),
                "testTotal": len(lesson.get("test_questions") or []),
            }
        return {"student": self._public_student(student), "lesson": lesson_payload}

    async def dashboard(self, user):
        async with self.lock:
            data = self._load()
            student = self._require_bound_student(data, user)
            return self._dashboard_payload(data, student)

    async def create_lesson(self, student_id, notes_source_path, original_name, generated):
        async with self.lock:
            data = self._load()
            student = data["students"].get(str(student_id))
            if not student:
                raise StudentLearningError("Ученик не найден")
            lesson_id = uuid.uuid4().hex[:20]
            lesson_dir = os.path.join(self.files_directory, student["id"], lesson_id)
            os.makedirs(lesson_dir, mode=0o700, exist_ok=True)
            notes_path = os.path.join(lesson_dir, "notes.pdf")
            shutil.copyfile(notes_source_path, notes_path)
            os.chmod(notes_path, 0o600)
            homework_path = generated.get("homework_path")
            if homework_path:
                final_homework_path = os.path.join(lesson_dir, "homework.pdf")
                shutil.copyfile(homework_path, final_homework_path)
                os.chmod(final_homework_path, 0o600)
            else:
                final_homework_path = None
            data["lessons"][lesson_id] = {
                "id": lesson_id,
                "student_id": student["id"],
                "title": str(generated.get("title") or os.path.splitext(original_name)[0])[:160],
                "notes_path": notes_path,
                "homework_path": final_homework_path,
                "test_questions": generated.get("test_questions") or [],
                "homework_tasks": generated.get("homework_tasks") or [],
                "next_topic": str(generated.get("next_topic") or "")[:500],
                "created_at": _now_iso(),
                "generation_status": generated.get("generation_status", "ready"),
            }
            self._save(data)
            return data["lessons"][lesson_id]

    async def open_lesson(self, user, lesson_id):
        async with self.lock:
            data = self._load()
            student = self._require_bound_student(data, user)
            lesson = data["lessons"].get(str(lesson_id))
            if not lesson or lesson["student_id"] != student["id"]:
                raise StudentLearningError("Материал не найден")
            if not lesson.get("opened_by_student_at"):
                lesson["opened_by_student_at"] = _now_iso()
                self._save(data)
            return self._dashboard_payload(data, student)

    async def confirm_reading(self, user, lesson_id):
        async with self.lock:
            data = self._load()
            student = self._require_bound_student(data, user)
            lesson = data["lessons"].get(str(lesson_id))
            if not lesson or lesson["student_id"] != student["id"]:
                raise StudentLearningError("Материал не найден")
            lesson["reading_confirmed_at"] = _now_iso()
            self._save(data)
            return self._dashboard_payload(data, student)

    async def material_path(self, user, lesson_id, kind):
        async with self.lock:
            data = self._load()
            student = self._require_bound_student(data, user)
            lesson = data["lessons"].get(str(lesson_id))
            if not lesson or lesson["student_id"] != student["id"]:
                raise StudentLearningError("Материал не найден")
            field = "notes_path" if kind == "notes" else "homework_path" if kind == "homework" else None
            path = lesson.get(field) if field else None
            if not path or not os.path.isfile(path):
                raise StudentLearningError("Файл пока не готов")
            return path, lesson

    async def test(self, user, lesson_id):
        async with self.lock:
            data = self._load()
            student = self._require_bound_student(data, user)
            lesson = data["lessons"].get(str(lesson_id))
            if not lesson or lesson["student_id"] != student["id"]:
                raise StudentLearningError("Тест не найден")
            unlocked = bool(lesson.get("reading_confirmed_at"))
            if not unlocked and lesson.get("opened_by_student_at"):
                try:
                    unlocked = _now() >= datetime.fromisoformat(lesson["opened_by_student_at"]) + timedelta(minutes=10)
                except ValueError:
                    pass
            if not unlocked:
                raise StudentLearningError("Сначала изучите конспект или подождите 10 минут после открытия")
            questions = []
            for index, item in enumerate(lesson.get("test_questions") or []):
                questions.append({
                    "id": index,
                    "question": item.get("question", ""),
                    "options": item.get("options", []),
                })
            return {"lessonId": lesson["id"], "title": lesson.get("title"), "questions": questions}

    async def submit_test(self, user, lesson_id, answers):
        async with self.lock:
            data = self._load()
            student = self._require_bound_student(data, user)
            lesson = data["lessons"].get(str(lesson_id))
            if not lesson or lesson["student_id"] != student["id"]:
                raise StudentLearningError("Тест не найден")
            questions = lesson.get("test_questions") or []
            if not isinstance(answers, list) or len(answers) != len(questions):
                raise StudentLearningError("Ответьте на все вопросы")
            score = sum(
                int(answer) == int(question.get("correct_index", -1))
                for answer, question in zip(answers, questions)
            )
            lesson["test_score"] = score
            lesson["test_completed_at"] = _now_iso()
            self._save(data)
            return {"score": score, "total": len(questions)}

    async def save_submission(self, user, lesson_id, uploads):
        async with self.lock:
            data = self._load()
            student = self._require_bound_student(data, user)
            lesson = data["lessons"].get(str(lesson_id))
            if not lesson or lesson["student_id"] != student["id"]:
                raise StudentLearningError("Домашнее задание не найдено")
            if not uploads:
                raise StudentLearningError("Прикрепите хотя бы один файл")
            submission_id = uuid.uuid4().hex[:20]
            target_dir = os.path.join(self.files_directory, student["id"], lesson["id"], "submissions", submission_id)
            os.makedirs(target_dir, mode=0o700, exist_ok=True)
            files = []
            for index, upload in enumerate(uploads):
                extension = ALLOWED_STUDENT_FILE_TYPES.get(upload["content_type"])
                if not extension:
                    raise StudentLearningError("Разрешены PDF, JPG, PNG и WebP")
                value = upload["data"]
                if not value or len(value) > MAX_STUDENT_FILE_BYTES:
                    raise StudentLearningError("Каждый файл должен быть меньше 15 МБ")
                path = os.path.join(target_dir, f"{index + 1}{extension}")
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as target:
                    target.write(value)
                files.append({
                    "path": path,
                    "name": str(upload.get("name") or os.path.basename(path))[:180],
                    "content_type": upload["content_type"],
                })
            data["submissions"][submission_id] = {
                "id": submission_id,
                "student_id": student["id"],
                "lesson_id": lesson["id"],
                "files": files,
                "created_at": _now_iso(),
                "reviewed_at": None,
            }
            self._save(data)
            return {
                "submissionId": submission_id,
                "student": self._public_student(student),
                "lessonTitle": lesson.get("title"),
                "files": len(files),
            }

    async def submissions_for_student(self, student_id):
        async with self.lock:
            data = self._load()
            result = []
            for item in data["submissions"].values():
                if item["student_id"] != student_id:
                    continue
                lesson = data["lessons"].get(item["lesson_id"], {})
                result.append({**item, "lesson_title": lesson.get("title", "Урок")})
            return sorted(result, key=lambda item: item["created_at"], reverse=True)

    async def reminder_candidates(self, now=None):
        now = now or _now()
        minute_key = now.strftime("%Y-%m-%dT%H:%M")
        async with self.lock:
            data = self._load()
            candidates = []
            changed = False
            for student in data["students"].values():
                reminder_time = student.get("reminder_time")
                if not student.get("telegram_user_id") or not reminder_time:
                    continue
                if now.strftime("%H:%M") != reminder_time:
                    continue
                lesson = self._latest_lesson(data, student["id"])
                if not lesson or not lesson.get("homework_path"):
                    continue
                submitted = any(
                    item["student_id"] == student["id"] and item["lesson_id"] == lesson["id"]
                    for item in data["submissions"].values()
                )
                if submitted or student.get("last_homework_reminder") == minute_key:
                    continue
                student["last_homework_reminder"] = minute_key
                changed = True
                candidates.append({
                    "telegram_user_id": int(student["telegram_user_id"]),
                    "lesson_title": lesson.get("title", "прошедшему уроку"),
                })
            if changed:
                self._save(data)
            return candidates
