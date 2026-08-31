import unittest
from unittest.mock import patch

from drive_questions import (
    FOLDER_MIME_TYPE,
    fetch_public_drive_index,
    fetch_expert_game_index,
    parse_drive_index,
    parse_expert_game_index,
    parse_extended_drive_index,
    parse_public_folder_html,
)
from questions import QuestionFormatError


class DriveQuestionTests(unittest.TestCase):
    def test_builds_question_from_filename_and_correct_answer(self):
        questions = parse_drive_index({"files": [{
            "id": "drive_file_6",
            "name": "6 - 120.png",
            "grade": 8,
            "mimeType": "image/png",
        }]})
        question = questions[0]
        self.assertEqual(question.grade, 8)
        self.assertEqual(question.options[question.correct_index], "120")
        self.assertIn("drive_file_6", question.image_url)

    def test_supports_decimal_comma_and_unicode_minus(self):
        questions = parse_drive_index({"files": [
            {"id": "decimal_file", "name": "7 — 2,5.jpg", "grade": 11, "mimeType": "image/jpeg"},
            {"id": "negative_file", "name": "8 - −3.webp", "grade": 11, "mimeType": "image/webp"},
        ]})
        self.assertEqual(questions[0].options[questions[0].correct_index], "2,5")
        self.assertEqual(questions[1].options[questions[1].correct_index], "-3")

    def test_supports_negative_answer_in_parentheses(self):
        questions = parse_drive_index({"files": [{
            "id": "parenthesised_negative",
            "name": "52 - (-1).png",
            "grade": 11,
            "mimeType": "image/png",
        }]})
        question = questions[0]
        self.assertEqual(question.options[question.correct_index], "-1")
        self.assertEqual(question.solution, "Правильный ответ: -1.")

    def test_rejects_image_without_answer_in_name(self):
        with self.assertRaises(QuestionFormatError):
            parse_drive_index({"files": [{
                "id": "bad_file",
                "name": "6.png",
                "grade": 9,
                "mimeType": "image/png",
            }]})


class _FakeResponse:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    async def text(self):
        return self.value


class _FakeSession:
    def get(self, url, **_kwargs):
        folder_id = url.split('/folders/', 1)[1].split('?', 1)[0]
        return _FakeResponse(folder_id)


class DriveFolderSeparationTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_part_subfolder_never_enters_first_part(self):
        folders = {
            "root": [
                {"id": f"grade-{grade}", "name": f"{grade} класс", "mimeType": FOLDER_MIME_TYPE}
                for grade in (8, 9, 10, 11)
            ],
            "grade-8": [
                {"id": "first-8", "name": "6 - 12.png", "mimeType": "image/png"},
                {"id": "second-folder-8", "name": "2 часть", "mimeType": FOLDER_MIME_TYPE},
            ],
            "grade-9": [{"id": "first-9", "name": "6 - 9.png", "mimeType": "image/png"}],
            "grade-10": [{"id": "first-10", "name": "6 - 10.png", "mimeType": "image/png"}],
            "grade-11": [{"id": "first-11", "name": "6 - 11.png", "mimeType": "image/png"}],
            "second-folder-8": [{"id": "second-8", "name": "1 - 42.png", "mimeType": "image/png"}],
        }
        with patch("drive_questions.parse_public_folder_html", side_effect=lambda marker: folders[marker]):
            payload = await fetch_public_drive_index(_FakeSession(), "root")
        self.assertEqual({item["id"] for item in payload["files"]}, {"first-8", "first-9", "first-10", "first-11"})
        self.assertEqual([item["id"] for item in payload["extendedFiles"]], ["second-8"])

    async def test_expert_bank_reads_solutions_and_answers_folders(self):
        folders = {
            "expert-root": [
                {"id": "solutions-folder", "name": "Решения", "mimeType": FOLDER_MIME_TYPE},
                {"id": "answers-folder", "name": "Ответы", "mimeType": FOLDER_MIME_TYPE},
            ],
            "solutions-folder": [{"id": "work-1", "name": "1 - 1", "mimeType": "image/jpeg"}],
            "answers-folder": [{"id": "answer-1", "name": "1", "mimeType": "image/png"}],
        }
        with patch("drive_questions.parse_public_folder_html", side_effect=lambda marker: folders[marker]):
            payload = await fetch_expert_game_index(_FakeSession(), "expert-root")
        tasks = parse_expert_game_index(payload)
        self.assertEqual(tasks[0]["number"], 1)
        self.assertEqual(tasks[0]["expertScore"], 1)
        self.assertIn("work-1", tasks[0]["imageUrl"])
        self.assertIn("answer-1", tasks[0]["answerImageUrl"])

    def test_expert_bank_requires_matching_answer_and_valid_score(self):
        with self.assertRaisesRegex(QuestionFormatError, "нет файла Ответы/1"):
            parse_expert_game_index({
                "solutions": [{"id": "work-1", "name": "1 - 1", "mimeType": "image/jpeg"}],
                "answers": [],
            })
        with self.assertRaisesRegex(QuestionFormatError, "выше максимума"):
            parse_expert_game_index({
                "solutions": [{"id": "work-1", "name": "1 - 3", "mimeType": "image/jpeg"}],
                "answers": [{"id": "answer-1", "name": "1", "mimeType": "image/png"}],
            }, max_score=2)

    def test_rejects_duplicate_number_inside_one_grade(self):
        with self.assertRaisesRegex(QuestionFormatError, "повторяется номер 6"):
            parse_drive_index({"files": [
                {"id": "first", "name": "6 - 120.png", "grade": 8, "mimeType": "image/png"},
                {"id": "second", "name": "6 - 42.png", "grade": 8, "mimeType": "image/png"},
            ]})

    def test_ignores_verified_legacy_files_one_to_five(self):
        questions = parse_drive_index({"files": [
            {"id": "legacy", "name": "1", "grade": 8, "mimeType": "image/png"},
            {"id": "new", "name": "6 - 120", "grade": 8, "mimeType": "image/png"},
        ]})
        self.assertEqual(len(questions), 1)
        self.assertIn("№6", questions[0].question)

    def test_rejects_new_numeric_file_without_answer(self):
        with self.assertRaises(QuestionFormatError):
            parse_drive_index({"files": [{
                "id": "missing_answer", "name": "6", "grade": 10, "mimeType": "image/png"
            }]})

    def test_parses_public_drive_payload(self):
        drive_json = '[[["file_id",["parent"],"6 - 120","image/png"]],null,null,null,[],1]'
        escaped = drive_json.replace('"', r'\x22').replace('[', r'\x5b').replace(']', r'\x5d')
        html = f"<script>window['_DRIVE_ivd'] = '{escaped}';</script>"
        self.assertEqual(parse_public_folder_html(html), [{
            "id": "file_id", "name": "6 - 120", "mimeType": "image/png"
        }])

    def test_builds_second_part_task_only_from_extended_files(self):
        tasks = parse_extended_drive_index({"extendedFiles": [{
            "id": "extended_file_1",
            "name": "1 - (-3).png",
            "grade": 9,
            "mimeType": "image/png",
        }]})
        self.assertEqual(len(tasks[9]), 1)
        self.assertEqual(tasks[9][0]["fields"][0]["answers"], ["-3"])
        self.assertIn("extended_file_1", tasks[9][0]["imageUrl"])

    def test_second_part_rejects_filename_without_answer(self):
        with self.assertRaisesRegex(QuestionFormatError, "2 часть"):
            parse_extended_drive_index({"extendedFiles": [{
                "id": "extended_file_2", "name": "2.png", "grade": 11, "mimeType": "image/png"
            }]})


if __name__ == "__main__":
    unittest.main()
