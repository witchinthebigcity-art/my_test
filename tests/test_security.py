import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer

TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abc"
os.environ.setdefault("TOKEN", TOKEN)
os.environ.setdefault("WEBAPP_URL", "https://example.invalid")
import bot
from community import CommunityError, CommunityStore, MOSCOW, validate_telegram_init_data


def signed(user, **extra):
    values = {"auth_date": str(int(time.time())), "user": json.dumps(user), **extra}
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


class StrictTelegramAuthTests(unittest.TestCase):
    def test_rejects_bot_channel_and_malformed_user_even_if_signed(self):
        for user in ([], "user", {}, {"id": -100123}, {"id": True}, {"id": "123"},
                     {"id": 123, "is_bot": True}, {"id": 123, "type": "channel"}, {"id": 2**52}):
            with self.subTest(user=user), self.assertRaises(CommunityError):
                validate_telegram_init_data(signed(user), TOKEN)

    def test_real_user_may_open_app_from_channel_link(self):
        user = {"id": 123, "first_name": "Ученик"}
        self.assertEqual(validate_telegram_init_data(signed(user, chat_type="channel"), TOKEN), user)

    def test_rejects_duplicate_fields_future_and_expired_sessions(self):
        user = {"id": 123}
        cases = [signed(user) + "&user=" + json.dumps(user),
                 signed(user, auth_date=str(int(time.time()) + 3600)),
                 signed(user, auth_date=str(int(time.time()) - 86401))]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(CommunityError):
                validate_telegram_init_data(value, TOKEN)


class PrivacyApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = CommunityStore(str(Path(self.directory.name) / "community.json"))
        self.results = Path(self.directory.name) / "results.json"
        self.a = {"id": 901, "username": "test_a"}
        self.b = {"id": 902, "username": "test_b"}
        self.c = {"id": 903, "username": "test_c"}
        self.profiles = {}
        for user, nickname in ((self.a, "АльфаАудит"), (self.b, "БетаАудит"), (self.c, "ГаммаАудит")):
            self.profiles[user["id"]] = await self.store.update_profile(user, {
                "nickname": nickname, "grade": 8, "leaderboardConsent": True,
            })
        for name, value in (("TOKEN", TOKEN), ("community_store", self.store),
                            ("RESULTS_FILE", str(self.results)), ("_notify_social_user", AsyncMock())):
            mock = patch.object(bot, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.client = TestClient(TestServer(bot.create_app()))
        self.addAsyncCleanup(self.client.close)
        await self.client.start_server()

    def headers(self, user=None):
        return {"X-Telegram-Init-Data": signed(user or self.a)}

    def public_id(self, user):
        return self.profiles[user["id"]]["public_id"]

    async def befriend(self):
        req = await self.store.request_friend(self.a, self.public_id(self.b))
        await self.store.accept_friend(self.b, req["requestId"])

    async def test_private_routes_reject_anonymous_and_do_not_cache(self):
        for path in ("/stats", "/api/profile", "/api/friends", "/api/blocks",
                     "/api/leaderboard", "/api/participants/search?q=Аудит"):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 401)
                self.assertIn("no-store", response.headers["Cache-Control"])
        response = await self.client.post("/save", json={"user_id": 902, "isCorrect": True})
        self.assertEqual(response.status, 401)
        self.assertFalse(self.results.exists())

    async def test_forged_and_bot_sessions_do_not_reach_store(self):
        for value in (signed(self.a).replace("901", "902"), signed({"id": 909, "is_bot": True})):
            response = await self.client.post("/api/friends/" + self.public_id(self.b),
                                              headers={"X-Telegram-Init-Data": value})
            self.assertEqual(response.status, 401)
        self.assertEqual(self.store._load()["friendships"], [])

    async def test_stats_strict_owner_no_null_username_fallback(self):
        rows = [{"user_id": 901, "isCorrect": False, "topic": "Алгебра"},
                {"user_id": 902, "isCorrect": True, "topic": "Геометрия"}]
        self.results.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
        response = await self.client.get("/stats?username=test_b", headers=self.headers())
        data = await response.json()
        self.assertEqual((data["total"], data["correct"]), (1, 0))
        response = await self.client.get("/stats?user_id=902", headers=self.headers())
        self.assertEqual(response.status, 403)

    async def test_save_binds_owner_and_time_to_verified_user(self):
        payload = {"user_id": 902, "username": "test_b", "isCorrect": True,
                   "grade": 8, "questionId": "fake-test-only", "attemptKey": "test-run", "time": "fake"}
        response = await self.client.post("/save", json=payload, headers=self.headers())
        self.assertEqual(response.status, 200)
        row = json.loads(self.results.read_text())
        self.assertEqual((row["user_id"], row["username"]), (901, "test_a"))
        self.assertNotEqual(row["time"], "fake")
        self.assertEqual(self.results.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(self.store.path).stat().st_mode & 0o777, 0o600)

    async def test_search_needs_exact_nickname_and_is_rate_limited(self):
        response = await self.client.get("/api/participants/search?q=Бета", headers=self.headers())
        self.assertEqual((await response.json())["entries"], [])
        response = await self.client.get("/api/participants/search?q=бетааудит", headers=self.headers())
        self.assertEqual(len((await response.json())["entries"]), 1)
        for _ in range(18):
            await self.client.get("/api/participants/search?q=Бета", headers=self.headers())
        response = await self.client.get("/api/participants/search?q=Бета", headers=self.headers())
        self.assertEqual(response.status, 429)
        self.assertIn("Retry-After", response.headers)
        response = await self.client.get("/api/profile", headers=self.headers())
        self.assertEqual(response.status, 200)

    async def test_only_receiver_can_explicitly_accept_request(self):
        req = await self.store.request_friend(self.a, self.public_id(self.b))
        for user in (self.a, self.c):
            response = await self.client.post(f"/api/friend-requests/{req['requestId']}/accept", headers=self.headers(user))
            self.assertEqual(response.status, 422)
        with self.assertRaises(CommunityError):
            await self.store.request_friend(self.b, self.public_id(self.a))
        self.assertEqual((await self.store.friends(self.a))["friends"], [])
        response = await self.client.post(f"/api/friend-requests/{req['requestId']}/accept", headers=self.headers(self.b))
        self.assertEqual(response.status, 200)

    async def test_decline_cooldown_persists_after_reloading_store(self):
        req = await self.store.request_friend(self.a, self.public_id(self.b))
        await self.store.decline_friend(self.b, req["requestId"])
        with self.assertRaisesRegex(CommunityError, "7 дней"):
            await CommunityStore(self.store.path).request_friend(self.a, self.public_id(self.b))
        data = self.store._load()
        data["friendships"][0]["updated_at"] = (datetime.now(MOSCOW) - timedelta(days=8)).isoformat()
        self.store._save(data)
        self.assertEqual((await self.store.request_friend(self.a, self.public_id(self.b)))["status"], "pending")

    async def test_hourly_request_limit_persists(self):
        for i in range(6):
            profile = await self.store.update_profile({"id": 910 + i}, {
                "nickname": f"Участник{i}", "leaderboardConsent": True,
            })
            if i < 5:
                await self.store.request_friend(self.a, profile["public_id"])
            else:
                with self.assertRaisesRegex(CommunityError, "Лимит заявок"):
                    await CommunityStore(self.store.path).request_friend(self.a, profile["public_id"])

    async def test_request_preference_independent_of_ranking_and_existing_friends(self):
        await self.befriend()
        response = await self.client.post("/api/profile", json={"allowFriendRequests": False}, headers=self.headers(self.b))
        self.assertEqual(response.status, 200)
        self.assertTrue((await response.json())["leaderboard_consent"])
        with self.assertRaises(CommunityError):
            await self.store.request_friend(self.c, self.public_id(self.b))
        self.assertEqual(len((await self.store.friends(self.b))["friends"]), 1)
        response = await self.client.post("/api/profile", json={"allowFriendRequests": "false"}, headers=self.headers(self.b))
        self.assertEqual(response.status, 422)

    async def test_statistics_hidden_from_strangers_and_pending_requests(self):
        await self.store.record_attempt(self.b, {"grade": 8, "isCorrect": True, "questionId": "test-q"})
        req = await self.store.request_friend(self.a, self.public_id(self.b))
        self.assertIsNone((await self.store.participant(self.a, self.public_id(self.b)))["stats"])
        response = await self.client.get("/api/leaderboard?grade=8", headers=self.headers())
        self.assertEqual((await response.json())["entries"], [])
        await self.store.accept_friend(self.b, req["requestId"])
        self.assertIsNotNone((await self.store.participant(self.a, self.public_id(self.b)))["stats"])
        response = await self.client.get("/api/leaderboard?grade=8", headers=self.headers())
        self.assertEqual(len((await response.json())["entries"]), 1)
        response = await self.client.get("/api/leaderboard?grade=8", headers=self.headers(self.c))
        self.assertEqual((await response.json())["entries"], [])

    async def test_block_revokes_social_access_and_only_owner_can_remove_it(self):
        await self.befriend()
        await self.store.send_message(self.a, self.public_id(self.b), "Привет")
        invite = await self.store.create_battle_invite(self.a, self.public_id(self.b), 8)
        response = await self.client.post("/api/blocks/" + self.public_id(self.a), headers=self.headers(self.b))
        self.assertEqual(response.status, 200)
        self.assertEqual((await self.store.friends(self.a))["friends"], [])
        self.assertEqual((await self.store.battle_invites(self.b))["incoming"], [])
        for operation in (
            self.store.request_friend(self.a, self.public_id(self.b)),
            self.store.send_message(self.a, self.public_id(self.b), "Привет"),
            self.store.conversation(self.a, self.public_id(self.b)),
            self.store.create_battle_invite(self.a, self.public_id(self.b), 8),
            self.store.accept_battle_invite(self.b, invite["inviteId"], []),
            self.store.participant(self.a, self.public_id(self.b)),
        ):
            with self.assertRaises(CommunityError):
                await operation
        self.assertEqual((await self.store.search_participants(self.a, "БетаАудит"))["entries"], [])
        await self.store.block_participant(self.a, self.public_id(self.b), remove=True)
        self.assertTrue(self.store._is_blocked(self.store._load(), "901", "902"))
        response = await self.client.get("/api/blocks", headers=self.headers(self.b))
        entry = (await response.json())["entries"][0]
        self.assertNotIn("user_id", entry)
        self.assertNotIn("telegram_username", entry)
        await self.store.block_participant(self.b, self.public_id(self.a), remove=True)
        self.assertFalse(self.store._is_blocked(self.store._load(), "901", "902"))
        self.assertEqual((await self.store.friends(self.a))["friends"], [])

    async def test_runtime_files_not_exposed_as_static_assets(self):
        for path in ("/community.json", "/results.json", "/users.json", "/.env", "/solutions/private.jpg"):
            self.assertEqual((await self.client.get(path)).status, 404)


if __name__ == "__main__":
    unittest.main()
