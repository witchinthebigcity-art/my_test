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

        options = tuple(row[header_map[f"option_{number}"]].strip() for number in range(1, 5))
        topic = row[header_map["topic"]].strip()
        question_text = row[header_map["question"]].strip()
        solution = row[header_map["solution"]].strip()
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

        questions.append(
            Question(
                grade=grade,
                topic=topic,
                question=question_text,
                options=options,
                correct_index=correct_number - 1,
                solution=solution,
                image_url=image_url,
                solution_image_url=solution_image_url,
            )
        )

    if not questions:
        raise QuestionFormatError("В таблице нет активных заданий для 8–11 классов")
    return questions
