import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TOKEN", "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abc")
os.environ.setdefault("WEBAPP_URL", "https://example.com")
os.environ.setdefault("ADMIN_ID", "1")

import bot
from questions import Question, QuestionFormatError


class FakeMessage:
    def __init__(self, user_id=1):
        self.from_user = SimpleNamespace(id=user_id)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class AdminRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_panel_contains_refresh_button(self):
        message = FakeMessage()
        await bot.admin_panel(message)
        markup = message.answers[0][1]["reply_markup"]
        button = markup.inline_keyboard[0][0]
        self.assertEqual(button.callback_data, "admin_refresh_questions")

    async def test_refresh_reports_counts_for_every_grade(self):
        questions = [
            Question(grade=grade, topic="Тема", question="Задание", options=("1", "2", "3", "4"), correct_index=0, solution="Решение")
            for grade in (8, 9, 10, 11)
        ]
        message = FakeMessage()
        old_extended = bot.questions_cache["extended"]
        old_expert = bot.questions_cache["expert"]
        old_warnings = bot.questions_cache.get("expert_warnings", [])
        bot.questions_cache["extended"] = {grade: [object()] for grade in (8, 9, 10, 11)}
        bot.questions_cache["expert"] = {11: {13: [object(), object()]}}
        bot.questions_cache["expert_warnings"] = ["11 класс / 14 номер: не найдены Ответы, Критерии"]
        try:
            with patch.object(bot, "_load_questions", AsyncMock(return_value=questions)) as loader:
                await bot._refresh_questions_for_admin(message)
        finally:
            bot.questions_cache["extended"] = old_extended
            bot.questions_cache["expert"] = old_expert
            bot.questions_cache["expert_warnings"] = old_warnings
        loader.assert_awaited_once_with(force=True)
        report = message.answers[-1][0]
        for grade in (8, 9, 10, 11):
            self.assertIn(f"{grade} класс: 1", report)
            self.assertIn("2 часть: 1", report)
        self.assertIn("11 класс: 13 номер — 2 работ", report)
        self.assertIn("8 класс: нет готовых работ", report)
        self.assertIn("Пропущены незавершённые папки", report)

    async def test_failed_refresh_says_that_working_database_is_preserved(self):
        message = FakeMessage()
        with patch.object(
            bot,
            "_load_questions",
            AsyncMock(side_effect=QuestionFormatError("неверное имя файла")),
        ):
            await bot._refresh_questions_for_admin(message)
        self.assertIn("Рабочая версия сохранена без изменений", message.answers[-1][0])

    async def test_non_admin_cannot_use_callback(self):
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=999),
            answer=AsyncMock(),
            message=FakeMessage(999),
        )
        await bot.refresh_questions_button(callback)
        callback.answer.assert_awaited_once_with("Недостаточно прав", show_alert=True)
        self.assertEqual(callback.message.answers, [])

    def test_universe_entry_is_hidden_until_server_confirms_admin(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "index.html").read_text(encoding="utf-8")
        script = (root / "community.js").read_text(encoding="utf-8")
        self.assertRegex(html, r'id="adminUniverseButton"[^>]+hidden')
        self.assertRegex(html, r'id="adminUniverseHomePanel"[^>]+hidden')
        self.assertIn("element.hidden = !adminMode", script)


if __name__ == "__main__":
    unittest.main()
