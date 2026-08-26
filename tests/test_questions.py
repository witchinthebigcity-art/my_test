import unittest

from questions import QuestionFormatError, normalise_math_source, parse_questions_csv


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

    def test_repairs_common_spreadsheet_math_artifacts(self):
        self.assertEqual(normalise_math_source("x ≥q 2; S = 2pi R"), "x ≥ 2; S = 2π R")
        self.assertEqual(normalise_math_source("√(0),49"), "√(0,49)")
        self.assertEqual(normalise_math_source("√(6^)2 + 8² = 10"), "√(6² + 8²) = 10")
        self.assertEqual(normalise_math_source("10 - й член; x = 2 = > y = 4"), "10-й член; x = 2 ⇒ y = 4")
        self.assertEqual(normalise_math_source("y = √(x) - 5)"), "y = √(x - 5)")
        self.assertEqual(normalise_math_source("(2√(3)²"), "(2√(3))²")
        self.assertEqual(normalise_math_source("[3; + infty)"), "[3; + ∞)")
        self.assertEqual(normalise_math_source("углы 34°и 72°"), "углы 34° и 72°")
        self.assertEqual(normalise_math_source("на 2 - м году"), "на 2-м году")
        self.assertEqual(normalise_math_source("27^1/3"), "27^(1/3)")
        self.assertEqual(normalise_math_source("10^ - 1"), "10^(-1)")
        self.assertEqual(normalise_math_source("5^log_5 7"), "5^(log_5(7))")

    def test_repairs_verified_answer_keys_and_formula_tasks(self):
        csv_text = """Класс,Тема,Вопрос,Вариант 1,Вариант 2,Вариант 3,Вариант 4,Правильный ответ,Решение
9,Векторы,Найдите длину вектора вектор c(3; 4),5,7,25,1,4,√(3² + 4²) = 5
11,Уравнения,Решите уравнение: 2ˣ - 3 = 32,5,8,2,3,3,x - 3 = 5 ⇒ x = 8
11,Текстовые задачи,Температура $T = T_0 + kt. t при T = 100$,80,20,25,10,2,4t = 80 ⇒ t = 20
"""
        questions = parse_questions_csv(csv_text)

        self.assertEqual(questions[0].options[questions[0].correct_index], "5")
        self.assertEqual(questions[1].question, "Решите уравнение: 2^(x - 3) = 32.")
        self.assertEqual(questions[1].options[questions[1].correct_index], "8")
        self.assertIn("T₀ = 20", questions[2].question)
        self.assertIn("k = 4", questions[2].question)

    def test_rejects_duplicate_options_after_normalisation(self):
        csv_text = """Класс,Тема,Вопрос,Вариант 1,Вариант 2,Вариант 3,Вариант 4,Правильный ответ,Решение
8,Алгебра,Вопрос,1,1,2,3,1,Решение
"""
        with self.assertRaisesRegex(QuestionFormatError, "не должны повторяться"):
            parse_questions_csv(csv_text)

    def test_repairs_additional_verified_wrong_answer_keys(self):
        csv_text = """Класс,Тема,Вопрос,Вариант 1,Вариант 2,Вариант 3,Вариант 4,Правильный ответ,Решение
9,Вероятность,"Вероятность события А равна 0,4. Вероятность противоположного события?",0.6,0.4,1,0,3,"1 - 0,4 = 0,6"
10,Степени,Вычислите: 27^1/3,3,9,1,81,3,Корень кубический из 27
10,Логарифмы,Вычислите: lg 100,2,10,1,100,3,10² = 100
11,Производная,Точка экстремума y = eˣ - x.,0,1,e,нет,2,e^x = 1 ⇒ x = 0
"""
        questions = parse_questions_csv(csv_text)
        self.assertEqual(
            [question.options[question.correct_index] for question in questions],
            ["0.6", "3", "2", "0"],
        )
        self.assertEqual(questions[1].question, "Вычислите: 27^(1/3)")


if __name__ == "__main__":
    unittest.main()
