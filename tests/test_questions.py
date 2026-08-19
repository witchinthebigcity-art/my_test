import unittest

from questions import QuestionFormatError, parse_questions_csv


class ParseQuestionsCsvTests(unittest.TestCase):
    def test_parses_russian_headers_and_filters_unsupported_grades(self):
        csv_text = """Класс,Тема,Вопрос,Вариант 1,Вариант 2,Вариант 3,Вариант 4,Правильный ответ,Решение,Активно
7,Дроби,Сколько?,1,2,3,4,2,Объяснение,да
8,Алгебра,Решите x+1=2,0,1,2,3,2,x=1,да
11,Производная,Найдите производную,1,2,3,4,3,Правило,нет
"""
        questions = parse_questions_csv(csv_text)

        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].grade, 8)
        self.assertEqual(questions[0].correct_index, 1)

    def test_supports_existing_positional_layout(self):
        csv_text = """Старый класс,Старая тема,Текст,А,Б,В,Г,Ответ,Разбор
9,Геометрия,Вопрос,A,B,C,D,4,Решение
"""
        question = parse_questions_csv(csv_text)[0]

        self.assertEqual(question.grade, 9)
        self.assertEqual(question.options, ("A", "B", "C", "D"))
        self.assertEqual(question.correct_index, 3)

    def test_rejects_invalid_correct_answer(self):
        csv_text = """Класс,Тема,Вопрос,Вариант 1,Вариант 2,Вариант 3,Вариант 4,Правильный ответ,Решение
10,Тема,Вопрос,A,B,C,D,5,Решение
"""
        with self.assertRaises(QuestionFormatError):
            parse_questions_csv(csv_text)

    def test_converts_public_google_drive_image_link(self):
        csv_text = """Класс,Тема,Вопрос,Вариант 1,Вариант 2,Вариант 3,Вариант 4,Правильный ответ,Решение,Изображение
10,Графики,Выберите график,A,B,C,D,1,Разбор,https://drive.google.com/file/d/example-file-id/view?usp=sharing
"""
        question = parse_questions_csv(csv_text)[0]

        self.assertEqual(
            question.image_url,
            "https://drive.google.com/thumbnail?id=example-file-id&sz=w1600",
        )


if __name__ == "__main__":
    unittest.main()
