import os
import time
import unittest

from aiohttp.test_utils import TestClient, TestServer

os.environ.setdefault("TOKEN", "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abc")
os.environ.setdefault("WEBAPP_URL", "https://example.com")
os.environ.setdefault("ADMIN_ID", "1")

import bot
from questions import Question


class QuestionsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        bot.questions_cache["loaded_at"] = time.monotonic()
        bot.questions_cache["items"] = [
            Question(
                grade=8,
                topic="Алгебра",
                question="Вопрос",
                options=("A", "B", "C", "D"),
                correct_index=1,
                solution="Решение",
                image_url="https://example.com/question.png",
            ),
            Question(
                grade=11,
                topic="Производная",
                question="Вопрос 2",
                options=("A", "B", "C", "D"),
                correct_index=2,
                solution="Решение 2",
            ),
        ]
        self.client = TestClient(TestServer(bot.create_app()))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_returns_only_requested_grade_and_image(self):
        response = await self.client.get("/api/questions?grade=8")
        payload = await response.json()

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["questions"][0]["grade"], 8)
        self.assertEqual(
            payload["questions"][0]["imageUrl"],
            "https://example.com/question.png",
        )

    async def test_rejects_unsupported_grade(self):
        response = await self.client.get("/api/questions?grade=7")

        self.assertEqual(response.status, 400)


if __name__ == "__main__":
    unittest.main()
