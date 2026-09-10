import json
import os
import tempfile
import unittest
import hashlib
import hmac
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer

from student_learning import MOSCOW, StudentLearningError, StudentLearningStore, verify_password


TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abc"
os.environ.setdefault("TOKEN", TOKEN)
os.environ.setdefault("WEBAPP_URL", "https://example.invalid")
import bot


def signed(user):
    values = {"auth_date": str(int(time.time())), "user": json.dumps(user)}
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


class StudentLearningStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "student_learning.json"
        self.store = StudentLearningStore(str(self.path))
        self.student, self.password = await self.store.add_student(
            "@student_test", 9, "Подготовиться к ОГЭ", "Сильная геометрия",
            "Вт 18:00, Сб 12:00", "19:30", "Тестовый ученик",
        )
        self.user = {"id": 7001, "username": "student_test"}

    async def test_password_is_hashed_and_first_login_binds_telegram_id(self):
        stored = json.loads(self.path.read_text(encoding="utf-8"))["students"][self.student["id"]]
        self.assertNotIn(self.password, self.path.read_text(encoding="utf-8"))
        self.assertTrue(verify_password(self.password, stored["password_salt"], stored["password_hash"]))
        self.assertFalse((await self.store.status(self.user))["authenticated"])
        result = await self.store.login(self.user, self.password, "20:00")
        self.assertTrue(result["bound"])
        self.assertTrue((await self.store.status({"id": 7001, "username": "renamed_user"}))["authenticated"])

    async def test_wrong_username_cannot_claim_unbound_account_even_with_password(self):
        with self.assertRaises(StudentLearningError):
            await self.store.login({"id": 9000, "username": "other_user"}, self.password)
        stored = json.loads(self.path.read_text(encoding="utf-8"))["students"][self.student["id"]]
        self.assertIsNone(stored["telegram_user_id"])

    async def test_student_cannot_open_another_students_files(self):
        await self.store.login(self.user, self.password)
        second, second_password = await self.store.add_student(
            "second_student", 11, "ЕГЭ", "", "Пн 12:00", "18:00", "Второй"
        )
        second_user = {"id": 7002, "username": "second_student"}
        await self.store.login(second_user, second_password)
        notes = Path(self.directory.name) / "notes.pdf"
        homework = Path(self.directory.name) / "homework.pdf"
        notes.write_bytes(b"%PDF notes")
        homework.write_bytes(b"%PDF homework")
        lesson = await self.store.create_lesson(second["id"], str(notes), "notes.pdf", {
            "title": "Тригонометрия", "homework_path": str(homework),
            "test_questions": [{"question": "q", "options": ["a", "b"], "correct_index": 0}],
            "homework_tasks": ["task"],
        })
        with self.assertRaises(StudentLearningError):
            await self.store.material_path(self.user, lesson["id"], "notes")
        path, _ = await self.store.material_path(second_user, lesson["id"], "notes")
        self.assertTrue(os.path.isfile(path))

    async def test_test_unlock_and_scoring(self):
        await self.store.login(self.user, self.password)
        notes = Path(self.directory.name) / "notes.pdf"
        homework = Path(self.directory.name) / "homework.pdf"
        notes.write_bytes(b"%PDF notes")
        homework.write_bytes(b"%PDF homework")
        lesson = await self.store.create_lesson(self.student["id"], str(notes), "notes.pdf", {
            "title": "Квадратные уравнения", "homework_path": str(homework),
            "test_questions": [
                {"question": "q1", "options": ["a", "b", "c", "d"], "correct_index": 2, "explanation": "because c"},
                {"question": "q2", "options": ["a", "b", "c", "d"], "correct_index": 0, "explanation": "because a"},
            ],
            "homework_tasks": ["task"],
        })
        with self.assertRaises(StudentLearningError):
            await self.store.test(self.user, lesson["id"])
        await self.store.open_lesson(self.user, lesson["id"])
        await self.store.confirm_reading(self.user, lesson["id"])
        public_test = await self.store.test(self.user, lesson["id"])
        self.assertNotIn("correct_index", public_test["questions"][0])
        wrong = await self.store.check_test_answer(self.user, lesson["id"], 0, 1)
        self.assertFalse(wrong["correct"])
        self.assertEqual(wrong["correctIndex"], 2)
        self.assertEqual(wrong["explanation"], "because c")
        correct = await self.store.check_test_answer(self.user, lesson["id"], 1, 0)
        self.assertTrue(correct["correct"])
        self.assertEqual(correct["explanation"], "")
        self.assertEqual(await self.store.submit_test(self.user, lesson["id"], [2, 1]), {"score": 1, "total": 2})

    async def test_daily_reminder_stops_after_submission(self):
        await self.store.login(self.user, self.password, "19:30")
        notes = Path(self.directory.name) / "notes.pdf"
        homework = Path(self.directory.name) / "homework.pdf"
        notes.write_bytes(b"%PDF notes")
        homework.write_bytes(b"%PDF homework")
        lesson = await self.store.create_lesson(self.student["id"], str(notes), "notes.pdf", {
            "title": "Функции", "homework_path": str(homework), "test_questions": [], "homework_tasks": []
        })
        now = datetime(2026, 9, 7, 19, 30, tzinfo=MOSCOW)
        self.assertEqual(len(await self.store.reminder_candidates(now)), 1)
        self.assertEqual(len(await self.store.reminder_candidates(now)), 0)
        await self.store.save_submission(self.user, lesson["id"], [{
            "name": "work.jpg", "content_type": "image/jpeg", "data": b"jpeg-data",
        }])
        next_day = datetime(2026, 9, 8, 19, 30, tzinfo=MOSCOW)
        self.assertEqual(await self.store.reminder_candidates(next_day), [])

    async def test_no_reminder_is_sent_when_homework_is_not_attached(self):
        await self.store.login(self.user, self.password, "19:30")
        notes = Path(self.directory.name) / "notes.pdf"
        notes.write_bytes(b"%PDF notes")
        await self.store.create_lesson(self.student["id"], str(notes), "notes.pdf", {
            "title": "Только конспект", "test_questions": [], "homework_tasks": []
        })
        now = datetime(2026, 9, 7, 19, 30, tzinfo=MOSCOW)
        self.assertEqual(await self.store.reminder_candidates(now), [])


class AdminStudentFormTests(unittest.TestCase):
    def test_numbered_form_from_telegram_is_parsed(self):
        fields = bot.parse_admin_student_fields(
            "1. @whitarrr\n"
            "2. Класс 9\n"
            "3. Кирилл\n"
            "4. Сдача ОГЭ и поступление в лицей\n"
            "5. Нужны задачи высокого уровня сложности\n"
            "6. 6. Понедельник в 17:30, суббота в 14:00\n"
            "7. 13:00"
        )
        self.assertEqual(fields["username"], "whitarrr")
        self.assertEqual(fields["grade"], "9")
        self.assertEqual(fields["display_name"], "Кирилл")
        self.assertEqual(fields["lesson_schedule"], "Понедельник в 17:30, суббота в 14:00")
        self.assertEqual(fields["reminder_time"], "13:00")

    def test_labels_without_numbering_are_supported(self):
        fields = bot.parse_admin_student_fields(
            "Telegram username: student_test\n"
            "Класс: 11\n"
            "Имя для кабинета: Анна\n"
            "Глобальная цель на год: ЕГЭ\n"
            "Важные факты и особенности: любит геометрию\n"
            "Дни и время занятий: среда 18:00\n"
            "Время ежедневного напоминания: 20:30"
        )
        self.assertEqual(fields["username"], "student_test")
        self.assertEqual(fields["grade"], "11")
        self.assertEqual(fields["display_name"], "Анна")

    def test_field_specific_error_for_bad_username(self):
        with self.assertRaisesRegex(StudentLearningError, "Первая строка"):
            bot.parse_admin_student_fields(
                "1. неправильный юз\n2. 9\n3. Имя\n4. Цель\n5. Факты\n6. Время\n7. 13:00"
            )


class AdminManualLessonTests(unittest.TestCase):
    def test_manual_lesson_content_is_parsed(self):
        result = bot.parse_manual_lesson_content(
            "Тема: Квадратные уравнения\n"
            "Следующая тема: Теорема Виета\n\n"
            "ДЗ:\n"
            "1. Решить x² - 5x + 6 = 0\n"
            "2. Построить график функции\n\n"
            "ТЕСТ:\n"
            "1. Сколько корней может иметь квадратное уравнение?\n"
            "А) Только один\n"
            "Б) Не больше двух\n"
            "В) Только три\n"
            "Г) Бесконечно много\n"
            "Ответ: Б\n"
            "Пояснение: Степень уравнения равна двум\n\n"
            "2. Что показывает дискриминант?\n"
            "А) Количество корней\n"
            "Б) Коэффициент a\n"
            "В) Вершину параболы\n"
            "Г) Область определения\n"
            "Ответ: А\n"
            "Пояснение: Его знак определяет количество действительных корней"
        )
        self.assertEqual(result["title"], "Квадратные уравнения")
        self.assertEqual(result["next_topic"], "Теорема Виета")
        self.assertEqual(len(result["homework_tasks"]), 2)
        self.assertEqual(len(result["test_questions"]), 2)
        self.assertEqual(result["test_questions"][0]["correct_index"], 1)
        self.assertEqual(result["generation_status"], "manual")

    def test_manual_lesson_requires_homework_and_test_sections(self):
        with self.assertRaisesRegex(StudentLearningError, "ДЗ"):
            bot.parse_manual_lesson_content("Тема: Функции\nТЕСТ:\n")

    def test_test_text_or_pdf_extraction_format_is_parsed_separately(self):
        result = bot.parse_manual_test_content(
            "Тема: Линейные уравнения\n"
            "1. Чему равен x?\n"
            "А) 1\nБ) 2\nВ) 3\nГ) 4\n"
            "Правильный ответ: В\n"
            "Объяснение: После переноса слагаемого\nполучаем x = 3."
        )
        self.assertEqual(result["title"], "Линейные уравнения")
        self.assertEqual(result["test_questions"][0]["correct_index"], 2)
        self.assertIn("x = 3", result["test_questions"][0]["explanation"])

    def test_test_requires_explanation_for_each_wrong_answer(self):
        with self.assertRaisesRegex(StudentLearningError, "Пояснение"):
            bot.parse_manual_test_content(
                "1. Вопрос?\nА) 1\nБ) 2\nВ) 3\nГ) 4\nОтвет: А",
                fallback_title="Тема",
            )

    def test_homework_is_parsed_after_test(self):
        self.assertEqual(
            bot.parse_manual_homework_content("ДЗ:\n1. Решить № 5\n• Повторить формулы"),
            ["Решить № 5", "Повторить формулы"],
        )


class StudentLearningApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = StudentLearningStore(str(Path(self.directory.name) / "students.json"))
        self.student, self.password = await self.store.add_student(
            "api_student", 8, "Итоговая контрольная", "", "Ср 17:00", "18:00", "API ученик"
        )
        self.user = {"id": 8111, "username": "api_student", "first_name": "Аня"}
        mock = patch.object(bot, "student_learning_store", self.store)
        mock.start()
        self.addCleanup(mock.stop)
        self.client = TestClient(TestServer(bot.create_app()))
        self.addAsyncCleanup(self.client.close)
        await self.client.start_server()

    def headers(self):
        return {"X-Telegram-Init-Data": signed(self.user)}

    async def test_login_is_bound_to_signed_telegram_user_and_routes_are_private(self):
        anonymous = await self.client.get("/api/student/status")
        self.assertEqual(anonymous.status, 401)
        status = await self.client.get("/api/student/status", headers=self.headers())
        self.assertFalse((await status.json())["authenticated"])
        login = await self.client.post(
            "/api/student/login", headers=self.headers(),
            json={"password": self.password, "reminderTime": "18:15"},
        )
        self.assertEqual(login.status, 200)
        dashboard = await self.client.get("/api/student/dashboard", headers=self.headers())
        self.assertEqual(dashboard.status, 200)
        self.assertEqual((await dashboard.json())["student"]["grade"], 8)
        for response in (status, login, dashboard):
            self.assertIn("no-store", response.headers.get("Cache-Control", ""))

    async def test_single_question_check_returns_explanation_only_for_error(self):
        await self.store.login(self.user, self.password)
        notes = Path(self.directory.name) / "api-notes.pdf"
        homework = Path(self.directory.name) / "api-homework.pdf"
        notes.write_bytes(b"%PDF notes")
        homework.write_bytes(b"%PDF homework")
        lesson = await self.store.create_lesson(self.student["id"], str(notes), "notes.pdf", {
            "title": "Тест API",
            "homework_path": str(homework),
            "homework_tasks": ["Задача"],
            "test_questions": [{
                "question": "2 + 2?",
                "options": ["2", "3", "4", "5"],
                "correct_index": 2,
                "explanation": "Два плюс два равно четыре.",
            }],
        })
        await self.store.confirm_reading(self.user, lesson["id"])
        wrong = await self.client.post(
            f"/api/student/lessons/{lesson['id']}/test/check",
            headers=self.headers(),
            json={"questionIndex": 0, "answer": 1},
        )
        self.assertEqual(wrong.status, 200)
        wrong_payload = await wrong.json()
        self.assertFalse(wrong_payload["correct"])
        self.assertIn("четыре", wrong_payload["explanation"])
        correct = await self.client.post(
            f"/api/student/lessons/{lesson['id']}/test/check",
            headers=self.headers(),
            json={"questionIndex": 0, "answer": 2},
        )
        self.assertEqual((await correct.json())["explanation"], "")


if __name__ == "__main__":
    unittest.main()
