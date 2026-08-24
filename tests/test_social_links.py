import os
import unittest
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault("TOKEN", "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abc")
os.environ.setdefault("WEBAPP_URL", "https://example.com/app")
os.environ.setdefault("ADMIN_ID", "1")

import bot


class SocialNotificationLinkTests(unittest.TestCase):
    def setUp(self):
        self.original_url = bot.WEBAPP_URL

    def tearDown(self):
        bot.WEBAPP_URL = self.original_url

    def test_builds_chat_deep_link(self):
        bot.WEBAPP_URL = "https://example.com/app"

        result = bot._social_webapp_url({"view": "chat", "publicId": "abcdef123456"})
        parsed = urlsplit(result)

        self.assertEqual(parsed.path, "/app")
        self.assertEqual(parse_qs(parsed.query), {
            "v": ["19"],
            "view": ["chat"],
            "publicId": ["abcdef123456"],
        })

    def test_preserves_existing_query_for_battle_invite(self):
        bot.WEBAPP_URL = "https://example.com/app?theme=dark"

        result = bot._social_webapp_url({"view": "battle-invite", "invite": "123456abcdef"})
        parsed = urlsplit(result)

        self.assertEqual(parse_qs(parsed.query), {
            "theme": ["dark"],
            "v": ["19"],
            "view": ["battle-invite"],
            "invite": ["123456abcdef"],
        })


if __name__ == "__main__":
    unittest.main()
