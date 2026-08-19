import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from urllib.parse import urlencode

from community import CommunityError, CommunityStore, validate_nickname, validate_telegram_init_data
from questions import Question


TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abc"


def signed_init_data(user):
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "test-query",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


class TelegramAuthTests(unittest.TestCase):
    def test_validates_signed_user(self):
        user = {"id": 42, "first_name": "Анна", "username": "anna"}
        self.assertEqual(validate_telegram_init_data(signed_init_data(user), TOKEN)["id"], 42)

    def test_rejects_modified_data(self):
        value = signed_init_data({"id": 42, "first_name": "Анна"}).replace("test-query", "changed")
        with self.assertRaises(CommunityError):
            validate_telegram_init_data(value, TOKEN)


class NicknameTests(unittest.TestCase):
    def test_accepts_normal_nickname(self):
        self.assertEqual(validate_nickname("Геометр_11"), "Геометр_11")

    def test_rejects_profanity_and_fake_admin(self):
        for value in ("f.u.c.k", "a-d-m-i-n", "пиздец"):
            with self.subTest(value=value), self.assertRaises(CommunityError):
                validate_nickname(value)


class CommunityStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = CommunityStore(os.path.join(self.directory.name, "community.json"))
        self.user_a = {"id": 1, "first_name": "Аня", "username": "anya", "photo_url": "https://example.com/a.jpg"}
        self.user_b = {"id": 2, "first_name": "Борис", "username": "boris"}
        self.questions = [
            Question(grade=8, topic="Алгебра", question=f"Вопрос {number}", options=("1", "2", "3", "4"), correct_index=0, solution="Решение")
            for number in range(1, 7)
        ]

    async def asyncTearDown(self):
        self.directory.cleanup()

    async def test_leaderboard_exposes_only_public_fields_and_hides_opt_out(self):
        await self.store.update_profile(self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8})
        await self.store.update_profile(self.user_b, {"nickname": "Борис8", "leaderboardConsent": False, "grade": 8})
        await self.store.record_attempt(self.user_a, {"questionId": "q1", "grade": 8, "isCorrect": True, "attemptKey": "a1"})
        await self.store.record_attempt(self.user_b, {"questionId": "q2", "grade": 8, "isCorrect": True, "attemptKey": "b1"})

        leaderboard = await self.store.leaderboard("day", 8)
        self.assertEqual(len(leaderboard["entries"]), 1)
        entry = leaderboard["entries"][0]
        self.assertEqual(entry["nickname"], "Алгебра8")
        self.assertNotIn("user_id", entry)
        self.assertNotIn("username", entry)

    async def test_same_question_scores_only_once_per_day(self):
        await self.store.update_profile(self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8})
        first = await self.store.record_attempt(self.user_a, {"questionId": "q1", "grade": 8, "isCorrect": True, "attemptKey": "first"})
        second = await self.store.record_attempt(self.user_a, {"questionId": "q1", "grade": 8, "isCorrect": True, "attemptKey": "second"})
        self.assertTrue(first["saved"])
        self.assertFalse(second["saved"])

    async def test_matches_two_users_and_finishes_battle(self):
        await self.store.update_profile(self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8})
        await self.store.update_profile(self.user_b, {"nickname": "Геометр8", "leaderboardConsent": True, "grade": 8})
        battle_id = await self.store.join_battle(self.user_a, 8, self.questions)
        self.assertEqual(battle_id, await self.store.join_battle(self.user_b, 8, self.questions))
        question_map = {question.question_id: question for question in self.questions}
        state = await self.store.battle_state(self.user_a, battle_id, question_map)
        self.assertEqual(state["status"], "active")
        self.assertNotIn("id", state["opponent"])

        for question in state["questions"]:
            await self.store.answer_battle(self.user_a, battle_id, question["id"], 0, question_map)
            final = await self.store.answer_battle(self.user_b, battle_id, question["id"], 1, question_map)
        self.assertEqual(final["battle"]["status"], "complete")
        self.assertEqual(final["battle"]["me"]["score"], 0)
        self.assertEqual(final["battle"]["opponent"]["score"], 5)


if __name__ == "__main__":
    unittest.main()
