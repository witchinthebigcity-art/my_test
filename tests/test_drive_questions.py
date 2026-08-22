import unittest

from drive_questions import parse_drive_index, parse_public_folder_html
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

    def test_rejects_image_without_answer_in_name(self):
        with self.assertRaises(QuestionFormatError):
            parse_drive_index({"files": [{
                "id": "bad_file",
                "name": "6.png",
                "grade": 9,
                "mimeType": "image/png",
            }]})

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


if __name__ == "__main__":
    unittest.main()
