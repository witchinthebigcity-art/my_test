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
                {"question": "q1", "options": ["a", "b", "c", "d"], "correct_index": 2},
                {"question": "q2", "options": ["a", "b", "c", "d"], "correct_index": 0},
            ],
            "homework_tasks": ["task"],
        })
        with self.assertRaises(StudentLearningError):
            await self.store.test(self.user, lesson["id"])
        await self.store.open_lesson(self.user, lesson["id"])
        await self.store.confirm_reading(self.user, lesson["id"])
        public_test = await self.store.test(self.user, lesson["id"])
        self.assertNotIn("correct_index", public_test["questions"][0])
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


if __name__ == "__main__":
    unittest.main()
