import csv
import hashlib
import io
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlparse


SUPPORTED_GRADES = {8, 9, 10, 11}


class QuestionFormatError(ValueError):
    """Raised when the published Google Sheet cannot be parsed."""


def _normalise_header(value: str) -> str:
    value = value.strip().casefold().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", "", value)


HEADER_ALIASES = {
    "grade": {"класс", "grade", "class"},
    "topic": {"тема", "topic"},
    "question": {"вопрос", "задание", "question"},
    "option_1": {"вариант1", "ответ1", "option1"},
    "option_2": {"вариант2", "ответ2", "option2"},
    "option_3": {"вариант3", "ответ3", "option3"},
    "option_4": {"вариант4", "ответ4", "option4"},
    "correct": {
        "правильныйответ",
        "номерправильногоответа",
        "верныйответ",
        "correct",
        "correctanswer",
    },
    "solution": {"решение", "объяснение", "solution", "explanation"},
    "image_url": {
        "изображение",
        "картинка",
        "изображениезадания",
        "картинказадания",
        "image",
        "imageurl",
    },
    "solution_image_url": {
        "изображениерешения",
        "картинкарешения",
        "solutionimage",
        "solutionimageurl",
    },
    "active": {"активно", "показывать", "active", "enabled"},
}


@dataclass(frozen=True)
class Question:
    grade: int
    topic: str
    question: str
    options: tuple[str, str, str, str]
    correct_index: int
    solution: str
    image_url: str = ""
    solution_image_url: str = ""

    @property
    def question_id(self) -> str:
        source = (
            f"{self.grade}\n{self.topic}\n{self.question}\n"
            f"{'|'.join(self.options)}\n{self.image_url}"
        ).encode("utf-8")
        return hashlib.sha256(source).hexdigest()[:20]

    def as_dict(self) -> dict:
        return {
            "id": self.question_id,
            "grade": self.grade,
            "topic": self.topic,
            "question": self.question,
            "options": list(self.options),
            "correctIndex": self.correct_index,
            "solution": self.solution,
            "imageUrl": self.image_url,
            "solutionImageUrl": self.solution_image_url,
        }

    def as_public_dict(self) -> dict:
        """Return a question without the correct answer or solution."""
        return {
            "id": self.question_id,
            "grade": self.grade,
            "topic": self.topic,
            "question": self.question,
            "options": list(self.options),
            "imageUrl": self.image_url,
        }


def _build_header_map(header: list[str]) -> dict[str, int]:
    normalised = [_normalise_header(cell) for cell in header]
    mapping: dict[str, int] = {}
    for field, aliases in HEADER_ALIASES.items():
        normalised_aliases = {_normalise_header(alias) for alias in aliases}
        for index, cell in enumerate(normalised):
            if cell in normalised_aliases:
                mapping[field] = index
                break
    return mapping


def _is_active(value: str) -> bool:
    return value.strip().casefold() not in {"0", "нет", "false", "off", "неактивно"}


def normalise_math_source(value: str) -> str:
    """Repair common spreadsheet notation glitches before sending text to the client."""
    value = re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()
    value = value.replace("≥q", "≥").replace("≤q", "≤")
    value = value.replace("> =", "≥").replace("< =", "≤")
    value = re.sub(r"(?i)(?<![A-Za-zА-Яа-яЁё])pi(?![A-Za-zА-Яа-яЁё])", "π", value)
    value = re.sub(r"(?i)\binfty\b", "∞", value)
    value = re.sub(r"=\s*>", "⇒", value)
    value = re.sub(r"(\d+)\s+-\s+й\b", r"\1-й", value)
    value = re.sub(r"(\d+)\s+-\s+м\b", r"\1-м", value)
    value = re.sub(r"([°)\]])(?=[А-Яа-яЁё])", r"\1 ", value)
    value = re.sub(r"([?!;:])(?=\S)", r"\1 ", value)
    value = re.sub(r",(?=[A-Za-zА-Яа-яЁё])", ", ", value)
    # Keep fractional and negative powers together on narrow screens and in KaTeX.
    value = re.sub(r"\^\s*(\d+)\s*/\s*(\d+)", r"^(\1/\2)", value)
    value = re.sub(r"\^\s*-\s*([A-Za-z0-9]+)", r"^(-\1)", value)
    value = re.sub(
        r"([A-Za-z0-9)])\^\s*log_([A-Za-z0-9]+)\s*\(?([A-Za-z0-9]+)\)?",
        r"\1^(log_\2(\3))",
        value,
        flags=re.IGNORECASE,
    )

    # Google Sheets occasionally moves the decimal part outside sqrt parentheses.
    value = re.sub(r"√\((\d+)\),\s*(\d+)", r"√(\1,\2)", value)
    # Repair legacy exports such as √(6^)2 and an unmatched opening parenthesis.
    value = re.sub(
        r"√\(([^()]*)\^\)\s*([23])\s*([+-])\s*([^=]+?)(?=\s*=)",
        lambda match: f"√({match.group(1)}{'²' if match.group(2) == '2' else '³'} {match.group(3)} {match.group(4)})",
        value,
    )
    value = re.sub(
        r"√\(([^()]*)\^\)\s*([23])",
        lambda match: f"√({match.group(1)}{'²' if match.group(2) == '2' else '³'})",
        value,
    )
    value = re.sub(r"\(√\(([^()]*)\)([²³])$", r"(√(\1))\2", value)
    value = re.sub(r"\((\d+)√\(([^()]*)\)([²³])$", r"(\1√(\2))\3", value)
    value = re.sub(
        r"√\(([^()]*)\)\s*([+-])\s*([^()=]+)\)(?=\s*(?:=|$))",
        r"√(\1 \2 \3)",
        value,
    )
    return value


def _repair_known_question(
    question_text: str,
    options: tuple[str, str, str, str],
    correct_index: int,
    solution: str,
) -> tuple[str, tuple[str, str, str, str], int, str]:
    """Repair verified mistakes in the current published sheet at import time."""
    exact_answers = {
        "Найдите длину вектора вектор c(3; 4)": "5",
        "Найдите медиану упорядоченного ряда: 1, 2, 3, 4, 5": "3",
        "Монету бросают дважды. Вероятность того, что оба раза выпадет «орёл»?": "0.25",
        "Найдите значение выражения: cos(π/3)": "0.5",
        "Производная функции f(x) = sin x": "cos x",
        "Вероятность того, что ручка пишет плохо, равна 0,1. Какова вероятность того, что она пишет хорошо?": "0.9",
        "В прямоугольном треугольнике гипотенуза 10, катет 6. Найдите косинус прилежащего угла.": "0.6",
        "Мастер делает работу за 3 часа, ученик — за 6. За сколько часов сделают вместе?": "2",
        "Вероятность события А равна 0,4. Вероятность противоположного события?": "0.6",
        "Вычислите: 27^(1/3)": "3",
        "Вычислите: lg 100": "2",
        "Вычислите: log₃ (81)": "4",
        "Точка экстремума y = eˣ - x.": "0",
    }
    expected_answer = exact_answers.get(question_text)

    if question_text == "Вероятность болезни 0,1. Вероятность заболеть после трех контактов?":
        question_text = (
            "Вероятность заболеть после одного контакта равна 0,1. "
            "Какова вероятность не заболеть ни после одного из трёх независимых контактов?"
        )
        expected_answer = "0.729"
    elif question_text == "Решите уравнение: 2ˣ - 3 = 32":
        question_text = "Решите уравнение: 2^(x - 3) = 32."
        solution = "x - 3 = 5 ⇒ x = 8."
        expected_answer = "8"
    elif question_text == "Решите уравнение: 5 + 1 = 0,2":
        question_text = "Решите уравнение: 5^(x + 1) = 0,2."
        solution = "5^(x + 1) = 5^(-1) ⇒ x + 1 = -1 ⇒ x = -2."
        expected_answer = "-2"
    elif question_text == "Значение: cos² 15° - sin² 15°":
        options = ("√(3)/2", options[1], options[2], options[3])
        solution = "cos² 15° - sin² 15° = cos 30° = √(3)/2."
        expected_answer = "√(3)/2"
    elif question_text == "Упростите: (a³)^4 / a^10":
        solution = "a¹² / a¹⁰ = a²."
    elif question_text.startswith("Мощность P = I² R."):
        question_text = "Мощность: P = I²R. Найдите R, если P = 100, I = 2."
        solution = "R = P / I² = 100 / 4 = 25."
        expected_answer = "25"
    elif question_text.startswith("Закон Гука F = k · x."):
        question_text = "Закон Гука: F = kx. Найдите F, если k = 500, x = 0,02."
        solution = "F = 500 · 0,02 = 10."
        expected_answer = "10"
    elif question_text.startswith("Кинетическая энергия E = mv² / 2"):
        question_text = "Кинетическая энергия: E = mv² / 2. Найдите E, если m = 4, v = 3."
        solution = "E = 4 · 3² / 2 = 18."
        expected_answer = "18"
    elif question_text.startswith("Температура"):
        question_text = "Температура: T = T₀ + kt. Найдите t, если T = 100, T₀ = 20, k = 4."
        solution = "4t = 100 - 20 = 80 ⇒ t = 20."
        expected_answer = "20"

    if expected_answer is not None:
        normalised_expected = normalise_math_source(expected_answer).replace(" ", "").casefold()
        matching = [
            index for index, option in enumerate(options)
            if normalise_math_source(option).replace(" ", "").casefold() == normalised_expected
        ]
        if len(matching) != 1:
            raise QuestionFormatError(
                f"В исправляемом задании «{question_text}» не найден единственный ответ {expected_answer}"
            )
        correct_index = matching[0]

    return question_text, options, correct_index, solution


def _normalise_image_url(value: str, row_number: int) -> str:
    value = value.strip()
    if not value:
        return ""

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise QuestionFormatError(
            f"Строка {row_number}: ссылка на изображение должна начинаться с http:// или https://"
        )

    if parsed.netloc.casefold() in {"drive.google.com", "www.drive.google.com"}:
        file_id = ""
        path_match = re.search(r"/d/([^/]+)", parsed.path)
        if path_match:
            file_id = path_match.group(1)
        else:
            file_id = parse_qs(parsed.query).get("id", [""])[0]
        if not file_id:
            raise QuestionFormatError(
                f"Строка {row_number}: не удалось определить файл по ссылке Google Drive"
            )
        return f"https://drive.google.com/thumbnail?id={quote(file_id)}&sz=w1600"

    return value


def parse_questions_csv(csv_text: str) -> list[Question]:
    """Parse the published sheet while keeping compatibility with the old 9-column layout."""
    if not csv_text.strip():
        raise QuestionFormatError("Google Таблица вернула пустой файл")
    if csv_text.lstrip().startswith("<"):
        raise QuestionFormatError("Google Таблица вернула HTML вместо CSV")

    rows = list(csv.reader(io.StringIO(csv_text.lstrip("\ufeff"))))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        raise QuestionFormatError("В таблице нет заданий")

    header_map = _build_header_map(rows[0])
    required_fields = {
        "grade",
        "topic",
        "question",
        "option_1",
        "option_2",
        "option_3",
        "option_4",
        "correct",
        "solution",
    }
    if not required_fields.issubset(header_map):
        # Backwards compatibility with the existing sheet:
        # Класс, Тема, Вопрос, Вариант 1-4, Правильный ответ, Решение.
        if len(rows[0]) < 9:
            missing = ", ".join(sorted(required_fields - set(header_map)))
            raise QuestionFormatError(f"Не найдены обязательные столбцы: {missing}")
        header_map = {
            "grade": 0,
            "topic": 1,
            "question": 2,
            "option_1": 3,
            "option_2": 4,
            "option_3": 5,
            "option_4": 6,
            "correct": 7,
            "solution": 8,
        }

    questions: list[Question] = []
    max_required_index = max(header_map[field] for field in required_fields)

    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) <= max_required_index:
            continue

        if "active" in header_map:
            active_index = header_map["active"]
            if active_index < len(row) and not _is_active(row[active_index]):
                continue

        grade_match = re.search(r"\d+", row[header_map["grade"]])
        if not grade_match:
            continue
        grade = int(grade_match.group())
        if grade not in SUPPORTED_GRADES:
            continue

        try:
            correct_number = int(row[header_map["correct"]].strip())
        except ValueError as exc:
            raise QuestionFormatError(
                f"Строка {row_number}: правильный ответ должен быть числом от 1 до 4"
            ) from exc
        if correct_number not in {1, 2, 3, 4}:
            raise QuestionFormatError(
                f"Строка {row_number}: правильный ответ должен быть числом от 1 до 4"
            )

        options = tuple(
            normalise_math_source(row[header_map[f"option_{number}"]])
            for number in range(1, 5)
        )
        topic = normalise_math_source(row[header_map["topic"]])
        question_text = normalise_math_source(row[header_map["question"]])
        solution = normalise_math_source(row[header_map["solution"]])
        image_url = ""
        if "image_url" in header_map and header_map["image_url"] < len(row):
            image_url = _normalise_image_url(row[header_map["image_url"]], row_number)
        solution_image_url = ""
        if "solution_image_url" in header_map and header_map["solution_image_url"] < len(row):
            solution_image_url = _normalise_image_url(
                row[header_map["solution_image_url"]], row_number
            )
        if not topic or not question_text or not all(options):
            raise QuestionFormatError(f"Строка {row_number}: заполнены не все обязательные ячейки")

        # Two known duplicate distractors in the current published sheet.
        if question_text.startswith("Найдите корень уравнения: |x - 5| = 2") and options == ("10", "7", "3", "10"):
            options = ("10", "7", "3", "5")
        elif question_text == "Найдите корень уравнения: √(2x + 1) = 3" and options == ("4", "1", "5", "4"):
            options = ("4", "1", "5", "8")

        question_text, options, correct_index, solution = _repair_known_question(
            question_text,
            options,
            correct_number - 1,
            solution,
        )
        compact_options = [re.sub(r"\s+", "", option).casefold() for option in options]
        if len(set(compact_options)) != 4:
            raise QuestionFormatError(f"Строка {row_number}: варианты ответа не должны повторяться")

        questions.append(
            Question(
                grade=grade,
                topic=topic,
                question=question_text,
                options=options,
                correct_index=correct_index,
                solution=solution,
                image_url=image_url,
                solution_image_url=solution_image_url,
            )
        )

    if not questions:
        raise QuestionFormatError("В таблице нет активных заданий для 8–11 классов")
    return questions
