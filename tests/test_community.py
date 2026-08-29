import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from urllib.parse import urlencode
from unittest.mock import patch

from community import (
    CommunityError,
    CommunityStore,
    decode_avatar_data_url,
    validate_message_text,
    validate_nickname,
    validate_telegram_init_data,
)
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

    def test_moderates_private_messages(self):
        self.assertEqual(validate_message_text("  Привет!\nКак дела?  "), "Привет!\nКак дела?")
        with self.assertRaises(CommunityError):
            validate_message_text("ты мудак")


class AvatarTests(unittest.TestCase):
    def test_accepts_real_image_signature_and_rejects_fake_payload(self):
        encoded = base64.b64encode(b"\xff\xd8\xfftest-jpeg").decode()
        extension, payload = decode_avatar_data_url(f"data:image/jpeg;base64,{encoded}")
        self.assertEqual(extension, "jpg")
        self.assertTrue(payload.startswith(b"\xff\xd8\xff"))
        fake = base64.b64encode(b"not-an-image").decode()
        with self.assertRaises(CommunityError):
            decode_avatar_data_url(f"data:image/png;base64,{fake}")


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

        data = self.store._load()
        started = (datetime.now().astimezone() - timedelta(seconds=1)).isoformat()
        for player in data["battles"][battle_id]["players"].values():
            player["question_started_at"] = started
        self.store._save(data)

        for question in state["questions"]:
            await self.store.answer_battle(self.user_a, battle_id, question["id"], 0, question_map)
            final = await self.store.answer_battle(self.user_b, battle_id, question["id"], 1, question_map)
        self.assertEqual(final["battle"]["status"], "complete")
        self.assertEqual(final["battle"]["me"]["score"], 0)
        self.assertEqual(final["battle"]["opponent"]["score"], 5)

    async def test_battle_players_start_together_and_timeout_is_missed(self):
        await self.store.update_profile(self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8})
        await self.store.update_profile(self.user_b, {"nickname": "Геометр8", "leaderboardConsent": True, "grade": 8})
        battle_id = await self.store.join_battle(self.user_a, 8, self.questions)
        await self.store.join_battle(self.user_b, 8, self.questions)
        question_map = {question.question_id: question for question in self.questions}
        state_a = await self.store.battle_state(self.user_a, battle_id, question_map)
        state_b = await self.store.battle_state(self.user_b, battle_id, question_map)
        self.assertEqual(state_a["questionDeadlineAt"], state_b["questionDeadlineAt"])
        self.assertEqual(state_a["countdownUntil"], state_b["countdownUntil"])
        self.assertEqual(state_a["questionSeconds"], 30)
        self.assertIn("serverNowAt", state_a)
        self.assertGreater(state_a["countdownRemainingMs"], 0)
        self.assertGreater(state_a["questionRemainingMs"], 0)
        self.assertLessEqual(state_a["questionRemainingMs"], 33000)
        with self.assertRaisesRegex(CommunityError, "Старт"):
            await self.store.answer_battle(
                self.user_a, battle_id, state_a["questions"][0]["id"], 0, question_map
            )

        data = self.store._load()
        first_id = data["battles"][battle_id]["question_ids"][0]
        data["battles"][battle_id]["players"]["1"]["question_started_at"] = (
            datetime.now().astimezone() - timedelta(seconds=31)
        ).isoformat()
        self.store._save(data)

        expired = await self.store.battle_state(self.user_a, battle_id, question_map)
        self.assertEqual(expired["myAnswers"][first_id], -1)
        self.assertEqual(expired["currentQuestionIndex"], 1)
        self.assertEqual(expired["me"]["answered"], 0)
        self.assertEqual(expired["me"]["missed"], 1)
        with self.assertRaisesRegex(CommunityError, "30 секунд"):
            await self.store.answer_battle(self.user_a, battle_id, first_id, 0, question_map)

    async def test_starts_server_bot_when_human_opponent_is_not_found(self):
        await self.store.update_profile(self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8})
        battle_id = await self.store.join_battle(self.user_a, 8, self.questions)
        with open(self.store.path, "r", encoding="utf-8") as source:
            data = json.load(source)
        data["battles"][battle_id]["created_at"] = "2020-01-01T00:00:00+03:00"
        with open(self.store.path, "w", encoding="utf-8") as target:
            json.dump(data, target)

        question_map = {question.question_id: question for question in self.questions}
        state = await self.store.battle_state(self.user_a, battle_id, question_map)

        self.assertEqual(state["status"], "active")
        self.assertEqual(state["opponent"]["nickname"], "Матан-Бот")
        self.assertTrue(state["opponent"]["isBot"])

    async def test_leaving_active_battle_is_loss_without_reward(self):
        await self.store.update_profile(self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8})
        await self.store.update_profile(self.user_b, {"nickname": "Геометр8", "leaderboardConsent": True, "grade": 8})
        battle_id = await self.store.join_battle(self.user_a, 8, self.questions)
        await self.store.join_battle(self.user_b, 8, self.questions)
        question_map = {question.question_id: question for question in self.questions}

        result = await self.store.forfeit_battle(self.user_a, battle_id, question_map)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["forfeitedByMe"])
        self.assertEqual(result["reward"]["coins"], 0)

        stats_a = await self.store.battle_stats(self.user_a)
        stats_b = await self.store.battle_stats(self.user_b)
        self.assertEqual((stats_a["wins"], stats_a["losses"]), (0, 1))
        self.assertEqual((stats_b["wins"], stats_b["losses"]), (1, 0))
        self.assertEqual((await self.store.get_profile(self.user_a))["coins"], 0)
        self.assertEqual((await self.store.get_profile(self.user_b))["coins"], 10)

    async def test_stores_custom_avatar_under_random_public_name(self):
        encoded = base64.b64encode(b"\xff\xd8\xffavatar-bytes").decode()
        profile = await self.store.update_profile(
            self.user_a,
            {"avatarDataUrl": f"data:image/jpeg;base64,{encoded}"},
        )
        self.assertEqual(profile["avatar_source"], "custom")
        self.assertTrue(profile["avatar_url"].startswith("/avatars/"))
        filename = profile["avatar_url"].rsplit("/", 1)[-1]
        self.assertNotEqual(filename.split(".", 1)[0], str(self.user_a["id"]))
        stored_path = self.store.avatar_path(filename)
        self.assertTrue(os.path.isfile(stored_path))

        restored = await self.store.update_profile(self.user_a, {"useTelegramAvatar": True})
        self.assertEqual(restored["avatar_url"], self.user_a["photo_url"])
        self.assertFalse(os.path.exists(stored_path))

    async def test_friend_requests_use_public_ids_and_hide_telegram_ids(self):
        profile_a = await self.store.update_profile(
            self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8}
        )
        profile_b = await self.store.update_profile(
            self.user_b, {"nickname": "Геометр8", "leaderboardConsent": True, "grade": 8}
        )
        search = await self.store.search_participants(self.user_a, "Геометр")
        self.assertEqual(search["entries"][0]["publicId"], profile_b["public_id"])
        self.assertNotIn("user_id", search["entries"][0])
        self.assertNotIn("username", search["entries"][0])

        created = await self.store.request_friend(self.user_a, profile_b["public_id"])
        self.assertEqual(created["status"], "pending")
        incoming = await self.store.friends(self.user_b)
        self.assertEqual(incoming["incoming"][0]["participant"]["publicId"], profile_a["public_id"])
        await self.store.accept_friend(self.user_b, incoming["incoming"][0]["id"])
        friends = await self.store.friends(self.user_a)
        self.assertEqual(friends["friends"][0]["participant"]["friendshipStatus"], "friends")

    async def test_messages_are_private_to_accepted_friends(self):
        profile_b = await self.store.update_profile(
            self.user_b, {"nickname": "Геометр8", "leaderboardConsent": True, "grade": 8}
        )
        with self.assertRaises(CommunityError):
            await self.store.send_message(self.user_a, profile_b["public_id"], "Привет")

        request = await self.store.request_friend(self.user_a, profile_b["public_id"])
        await self.store.accept_friend(self.user_b, request["requestId"])
        sent = await self.store.send_message(self.user_a, profile_b["public_id"], "Решим задачу?")
        self.assertTrue(sent["message"]["mine"])
        conversation = await self.store.conversation(self.user_b, (await self.store.get_profile(self.user_a))["public_id"])
        self.assertEqual(conversation["messages"][0]["text"], "Решим задачу?")
        self.assertFalse(conversation["messages"][0]["mine"])
        self.assertNotIn("sender_id", conversation["messages"][0])

    async def test_invited_friends_can_battle_across_different_grades(self):
        profile_a = await self.store.update_profile(
            self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8}
        )
        profile_b = await self.store.update_profile(
            self.user_b, {"nickname": "Геометр9", "leaderboardConsent": True, "grade": 9}
        )
        request = await self.store.request_friend(self.user_a, profile_b["public_id"])
        await self.store.accept_friend(self.user_b, request["requestId"])

        questions_10 = [
            Question(grade=10, topic="Алгебра", question=f"Вопрос 10-{number}", options=("1", "2", "3", "4"), correct_index=0, solution="Решение")
            for number in range(1, 7)
        ]
        invite = await self.store.create_battle_invite(self.user_a, profile_b["public_id"], 10)
        self.assertEqual((await self.store.get_profile(self.user_a))["grade"], 8)
        accepted = await self.store.accept_battle_invite(self.user_b, invite["inviteId"], questions_10)
        question_map = {question.question_id: question for question in questions_10}
        state = await self.store.battle_state(self.user_b, accepted["battleId"], question_map)
        self.assertEqual(state["grade"], 10)
        self.assertEqual(state["status"], "active")
        self.assertEqual((await self.store.get_profile(self.user_b))["grade"], 9)

    async def test_accepting_friend_invite_cancels_pending_random_match(self):
        profile_a = await self.store.update_profile(
            self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8}
        )
        profile_b = await self.store.update_profile(
            self.user_b, {"nickname": "Геометр9", "leaderboardConsent": True, "grade": 9}
        )
        request = await self.store.request_friend(self.user_a, profile_b["public_id"])
        await self.store.accept_friend(self.user_b, request["requestId"])
        questions = [
            Question(grade=10, topic="Алгебра", question=f"Вопрос 10-{number}", options=("1", "2", "3", "4"), correct_index=0, solution="Решение")
            for number in range(1, 7)
        ]

        waiting_id = await self.store.join_battle(self.user_a, 10, questions)
        invite = await self.store.create_battle_invite(self.user_a, profile_b["public_id"], 10)
        accepted = await self.store.accept_battle_invite(self.user_b, invite["inviteId"], questions)

        self.assertNotEqual(accepted["battleId"], waiting_id)
        data = self.store._load()
        self.assertEqual(data["battles"][waiting_id]["status"], "cancelled")
        self.assertEqual(data["battles"][accepted["battleId"]]["status"], "active")

    async def test_daily_login_rewards_once_and_advances_streak(self):
        first = await self.store.claim_daily_login(self.user_a)
        self.assertTrue(first["claimed"])
        self.assertEqual(first["reward"], 10)
        self.assertEqual(first["coins"], 10)
        repeated = await self.store.claim_daily_login(self.user_a)
        self.assertFalse(repeated["claimed"])
        self.assertEqual(repeated["coins"], 10)

        with open(self.store.path, "r", encoding="utf-8") as source:
            data = json.load(source)
        data["profiles"]["1"]["last_login_date"] = (datetime.now().date() - timedelta(days=1)).isoformat()
        data["profiles"]["1"]["login_streak"] = 1
        with open(self.store.path, "w", encoding="utf-8") as target:
            json.dump(data, target)
        second_day = await self.store.claim_daily_login(self.user_a)
        self.assertEqual(second_day["streak"], 2)
        self.assertEqual(second_day["reward"], 15)

    async def test_daily_login_waits_for_manual_claim(self):
        status = await self.store.daily_login_status(self.user_a)
        self.assertFalse(status["claimedToday"])
        self.assertEqual(status["activeDay"], 1)
        self.assertEqual(status["activeReward"], 10)
        self.assertEqual(status["coins"], 0)

    async def test_sixth_day_wheel_awards_coupon_once_and_applies_it(self):
        await self.store.get_profile(self.user_a)
        data = self.store._load()
        profile = data["profiles"]["1"]
        profile["last_login_date"] = datetime.now().date().isoformat()
        profile["login_streak"] = 6
        profile["coins"] = 2000
        self.store._save(data)

        discount_prize = {"kind": "discount", "value": 20, "label": "Скидка 20%", "weight": 8}
        with patch("community.random.SystemRandom.choices", return_value=[discount_prize]):
            wheel = await self.store.spin_daily_wheel(self.user_a)
        self.assertEqual(wheel["prize"]["value"], 20)
        self.assertTrue(wheel["wheelClaimed"])
        with self.assertRaises(CommunityError):
            await self.store.spin_daily_wheel(self.user_a)

        purchased = await self.store.purchase_shop_item(self.user_a, "guide-algebra")
        self.assertEqual(purchased["discountApplied"], 20)
        self.assertEqual(purchased["paid"], 1200)
        self.assertEqual(purchased["coins"], 800)

    async def test_named_admin_has_unlimited_shop_character_and_lives_flag(self):
        admin = {"id": 77, "first_name": "Данил", "username": "supertutor15"}
        status = await self.store.daily_login_status(admin)
        self.assertTrue(status["admin"])
        shop = await self.store.purchase_shop_item(admin, "gadget-tablet")
        self.assertTrue(shop["admin"])
        self.assertEqual(shop["coins"], 0)
        character = await self.store.purchase_character(admin, "premium-cardboard-bot")
        self.assertTrue(character["admin"])
        self.assertEqual(character["coins"], 0)

    async def test_battle_win_coins_have_no_daily_cap_and_reward_wheel_unlocks(self):
        await self.store.update_profile(self.user_a, {"nickname": "Алгебра8", "leaderboardConsent": True, "grade": 8})
        await self.store.update_profile(self.user_b, {"nickname": "Геометр8", "leaderboardConsent": True, "grade": 8})
        data = self.store._load()
        for number in range(1, 6):
            battle_id = f"battle-{number}"
            battle = {
                "id": battle_id,
                "grade": 8,
                "status": "complete",
                "created_at": datetime.now().astimezone().isoformat(),
                "started_at": datetime.now().astimezone().isoformat(),
                "question_ids": [],
                "players": {
                    "1": {"score": 5, "answers": {}, "finished_at": datetime.now().astimezone().isoformat()},
                    "2": {"score": 2, "answers": {}, "finished_at": datetime.now().astimezone().isoformat()},
                },
            }
            data["battles"][battle_id] = battle
            self.store._award_battle_bonus(data, battle)
        self.store._save(data)

        profile = (await self.store.get_profile(self.user_a))
        self.assertEqual(profile["coins"], 50)
        stored_data = self.store._load()
        reward_status = self.store._battle_reward_status(stored_data, stored_data["profiles"]["1"], "1")
        self.assertEqual(reward_status["winsToday"], 5)
        self.assertTrue(reward_status["daily"]["available"])
        stats = await self.store.battle_stats(self.user_a)
        self.assertEqual(stats["wins"], 5)
        self.assertEqual(stats["winPercent"], 100.0)
        self.assertEqual(stats["coinsToday"], 50)

    async def test_shop_purchase_last_thirty_days_and_can_be_equipped(self):
        await self.store.get_profile(self.user_a)
        data = self.store._load()
        data["profiles"]["1"]["coins"] = 6000
        self.store._save(data)
        purchased = await self.store.purchase_shop_item(self.user_a, "gadget-phone")
        self.assertEqual(purchased["coins"], 1000)
        self.assertEqual(purchased["purchasedItem"]["name"], "Смартфон")
        phone = next(item for item in purchased["items"] if item["id"] == "gadget-phone")
        self.assertTrue(phone["owned"])
        equipped = await self.store.equip_shop_item(self.user_a, "gadget-phone")
        self.assertEqual(equipped["equippedItems"]["accessory"], "gadget-phone")
        expires = datetime.fromisoformat(phone["ownedUntil"])
        self.assertGreater(expires, datetime.now(expires.tzinfo) + timedelta(days=29))

    async def test_purchased_guides_are_returned_in_profile(self):
        await self.store.get_profile(self.user_a)
        data = self.store._load()
        data["profiles"]["1"]["coins"] = 2000
        self.store._save(data)
        purchased = await self.store.purchase_shop_item(self.user_a, "guide-algebra")
        self.assertEqual(purchased["paid"], 1500)
        self.assertEqual(purchased["coins"], 500)
        self.assertEqual(purchased["purchasedItem"]["slot"], "guide")
        profile = await self.store.get_profile(self.user_a)
        self.assertEqual([item["id"] for item in profile["materials"]], ["guide-algebra"])

    async def test_shop_catalog_is_tripled_and_headphones_removed(self):
        catalog = await self.store.shop_catalog(self.user_a)
        departments = {
            name: [item for item in catalog["items"] if item["department"] == name]
            for name in ("book", "magazine", "laptop")
        }
        self.assertEqual(len(departments["book"]), 9)
        self.assertEqual(len(departments["magazine"]), 24)
        self.assertEqual(len(departments["laptop"]), 18)
        self.assertNotIn("gadget-airpods", {item["id"] for item in catalog["items"]})
        self.assertNotIn("gadget-smart-ring", {item["id"] for item in catalog["items"]})
        self.assertEqual(
            {item["price"] for items in departments.values() for item in items},
            {1500, 2500, 5000, 10000},
        )

    async def test_global_character_catalog_and_purchases_persist(self):
        catalog = await self.store.character_catalog(self.user_a)
        self.assertEqual(len(catalog["characters"]), 17)
        basic = [item for item in catalog["characters"] if item["category"] == "basic"]
        premium = [item for item in catalog["characters"] if item["category"] == "premium"]
        self.assertEqual(len(basic), 9)
        self.assertEqual(len(premium), 8)
        self.assertEqual(sum(item["owned"] for item in catalog["characters"]), 7)
        self.assertTrue(all(item["price"] == 0 and item["owned"] for item in catalog["characters"][:7]))
        self.assertEqual(catalog["characters"][15]["name"], "Праздничный кузнец")
        self.assertEqual(catalog["characters"][15]["style"], "festive-forge")
        self.assertEqual(
            sorted(item["price"] for item in premium),
            [5000, 5000, 5000, 5000, 10000, 10000, 10000, 10000],
        )

        with open(self.store.path, "r", encoding="utf-8") as source:
            data = json.load(source)
        data["profiles"]["1"]["coins"] = 20000
        with open(self.store.path, "w", encoding="utf-8") as target:
            json.dump(data, target)
        cheapest = min(premium, key=lambda item: item["price"])
        purchased = await self.store.purchase_character(self.user_a, cheapest["id"])
        self.assertTrue(purchased["purchased"])
        self.assertEqual(purchased["coins"], 20000 - cheapest["price"])
        repeat = await self.store.purchase_character(self.user_a, cheapest["id"])
        self.assertFalse(repeat["purchased"])
        self.assertEqual(repeat["coins"], purchased["coins"])

    async def test_migrates_owned_grade_eight_character_to_global_catalog(self):
        await self.store.get_profile(self.user_a)
        with open(self.store.path, "r", encoding="utf-8") as source:
            data = json.load(source)
        profile = data["profiles"]["1"]
        profile["selected_characters"] = {"8": "g8-turbo-bomber"}
        profile["unlocked_characters"] = {"8": ["g8-turbo-bomber"]}
        with open(self.store.path, "w", encoding="utf-8") as target:
            json.dump(data, target)

        catalog = await self.store.character_catalog(self.user_a)
        turbo = next(item for item in catalog["characters"] if item["id"] == "g8-turbo-bomber")

        self.assertTrue(turbo["owned"])
        self.assertTrue(turbo["selected"])

    async def test_training_coins_are_idempotent_without_daily_cap(self):
        rewards = []
        for index in range(6):
            result = await self.store.award_training_coins(self.user_a, f"attempt:{index}:valid")
            rewards.append(result["awarded"])
        self.assertEqual(rewards, [10, 10, 10, 10, 10, 10])
        duplicate = await self.store.award_training_coins(self.user_a, "attempt:0:valid")
        self.assertEqual(duplicate["awarded"], 0)
        self.assertEqual(duplicate["reason"], "duplicate")

    async def test_three_battle_wins_unlock_one_weekly_daily_reward(self):
        await self.store.get_profile(self.user_a)
        data = self.store._load()
        now = datetime.now().astimezone().isoformat()
        for index in range(3):
            data["battles"][f"won-{index}"] = {
                "id": f"won-{index}", "status": "complete", "created_at": now,
                "completed_at": now, "players": {"1": {"score": 5}, "2": {"score": 2}},
            }
        self.store._save(data)

        status = self.store._battle_reward_status(data, data["profiles"]["1"], "1")
        self.assertTrue(status["daily"]["available"])
        reward = await self.store.spin_battle_reward(self.user_a, "daily")
        self.assertTrue(reward["spun"])
        self.assertEqual(reward["prize"]["validDays"], 7)
        self.assertFalse(reward["daily"]["available"])
        with self.assertRaises(CommunityError):
            await self.store.spin_battle_reward(self.user_a, "daily")

    async def test_thirty_distinct_winning_days_unlock_monthly_reward(self):
        await self.store.get_profile(self.user_a)
        data = self.store._load()
        today = datetime.now().astimezone().date()
        for offset in range(30):
            timestamp = datetime.combine(today - timedelta(days=offset), datetime.min.time()).astimezone().isoformat()
            data["battles"][f"streak-{offset}"] = {
                "id": f"streak-{offset}", "status": "complete", "created_at": timestamp,
                "completed_at": timestamp, "players": {"1": {"score": 4}, "2": {"score": 1}},
            }
        self.store._save(data)
        status = self.store._battle_reward_status(data, data["profiles"]["1"], "1")
        self.assertEqual(status["winningDaysInLast30"], 30)
        self.assertTrue(status["monthly"]["available"])


if __name__ == "__main__":
    unittest.main()
