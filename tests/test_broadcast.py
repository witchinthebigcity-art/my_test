import json
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("TOKEN", "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abc")
os.environ.setdefault("WEBAPP_URL", "https://example.com")
os.environ.setdefault("ADMIN_ID", "1")

from bot import load_user_ids, send_broadcast


class FakeBot:
    def __init__(self):
        self.copies = []
        self.texts = []

    async def copy_message(self, **kwargs):
        self.copies.append(kwargs)
        return SimpleNamespace(message_id=1000 + len(self.copies))

    async def send_message(self, **kwargs):
        self.texts.append(kwargs)
        return SimpleNamespace(message_id=2000 + len(self.texts))


class LoadUsersTests(unittest.TestCase):
    def test_loads_old_list_and_new_dictionary_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "users.json")
            with open(path, "w", encoding="utf-8") as target:
                json.dump([10, "20", 10, "bad"], target)
            self.assertEqual(load_user_ids(path), [10, 20])

            with open(path, "w", encoding="utf-8") as target:
                json.dump({"30": {"name": "Аня"}, "40": {}}, target)
            self.assertEqual(load_user_ids(path), [30, 40])


class BroadcastTests(unittest.IsolatedAsyncioTestCase):
    async def test_copies_media_message_to_every_user(self):
        fake_bot = FakeBot()
        source = SimpleNamespace(chat=SimpleNamespace(id=777), message_id=55)

        report = await send_broadcast(
            source_message=source,
            user_ids=[1, 2, 3],
            bot_client=fake_bot,
            delay=0,
        )

        self.assertEqual(len(report["sent"]), 3)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(fake_bot.copies[0], {"chat_id": 1, "from_chat_id": 777, "message_id": 55})

    async def test_sends_text_supplied_after_command(self):
        fake_bot = FakeBot()

        report = await send_broadcast(
            text="Новый урок уже доступен",
            user_ids=[4, 5],
            bot_client=fake_bot,
            delay=0,
        )

        self.assertEqual(len(report["sent"]), 2)
        self.assertEqual(fake_bot.texts[1]["text"], "Новый урок уже доступен")


if __name__ == "__main__":
    unittest.main()
