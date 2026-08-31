import ast
import asyncio
import hashlib
import json
import os
import random
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from questions import Question, QuestionFormatError, SUPPORTED_GRADES


IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
FILENAME_PATTERN = re.compile(
    r"^\s*(?P<number>\d+)\s*[-–—]\s*(?P<answer>.+?)(?:\.(?:jpe?g|png|webp))?\s*$",
    re.IGNORECASE,
)
LEGACY_FILENAME_PATTERN = re.compile(
    r"^\s*(?P<number>[1-5])(?:\.(?:jpe?g|png|webp))?\s*$",
    re.IGNORECASE,
)
PUBLIC_FOLDER_DATA_PATTERN = re.compile(
    r"window\['_DRIVE_ivd'\]\s*=\s*'(.*?)';",
    re.DOTALL,
)
PUBLIC_API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{30,50}")
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
DRIVE_FILES_API_URL = "https://www.googleapis.com/drive/v3/files"
EXPERT_SOLUTION_PATTERN = re.compile(
    r"^\s*(?P<number>\d+)\s*[-–—]\s*(?P<score>\d+)"
    r"(?:\.(?:jpe?g|png|webp))?\s*$",
    re.IGNORECASE,
)
EXPERT_ANSWER_PATTERN = re.compile(
    r"^\s*(?P<number>\d+)(?:\.(?:jpe?g|png|webp))?\s*$",
    re.IGNORECASE,
)


def _format_decimal(value: Decimal, comma: bool) -> str:
    if value == value.to_integral():
        result = str(int(value))
    else:
        result = format(value.normalize(), "f")
    return result.replace(".", ",") if comma else result


def _numeric_options(answer: str):
    source = answer.strip().replace("−", "-")
    parenthesised = re.fullmatch(r"\(\s*([+-]?\s*\d+(?:[.,]\d+)?)\s*\)", source)
    if parenthesised:
        source = parenthesised.group(1).replace(" ", "")
    source = source.replace(",", ".")
    try:
        value = Decimal(source)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    comma = "," in answer
    step = Decimal("1") if value == value.to_integral() else Decimal("0.1")
    if abs(value) >= 20:
        step = max(step, (abs(value) / Decimal("10")).quantize(Decimal("1")))
    candidates = [value, value - step, value + step, value + step * 2]
    options = [_format_decimal(item, comma) for item in candidates]
    return options, _format_decimal(value, comma)


def _answer_options(answer: str, seed: str):
    answer = answer.strip()
    numeric = _numeric_options(answer)
    if numeric is None:
        correct_answer = answer
        distractors = ["0", "1", "Нет решения", "Недостаточно данных"]
        options = [correct_answer] + [item for item in distractors if item != correct_answer][:3]
    else:
        options, correct_answer = numeric
    rng = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16))
    rng.shuffle(options)
    return tuple(options), options.index(correct_answer), correct_answer


def parse_drive_index(payload) -> list[Question]:
    """Convert the safe JSON index produced by the bundled Apps Script into questions."""
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list):
        raise QuestionFormatError("Индекс Google Drive должен содержать список files")

    questions = []
    errors = []
    seen_numbers = set()
    for item in files:
        if not isinstance(item, dict):
            continue
        try:
            grade = int(item.get("grade"))
        except (TypeError, ValueError):
            continue
        if grade not in SUPPORTED_GRADES or item.get("mimeType") not in IMAGE_TYPES:
            continue

        name = os.path.basename(str(item.get("name") or ""))
        match = FILENAME_PATTERN.match(name)
        if not match:
            # Files 1–5 already have verified answers in image_questions.csv.
            # They predate the filename convention and must not be duplicated.
            if LEGACY_FILENAME_PATTERN.match(name):
                continue
            errors.append(f"{grade} класс: {name}")
            continue

        number = int(match.group("number"))
        number_key = (grade, number)
        if number_key in seen_numbers:
            errors.append(f"{grade} класс: повторяется номер {number}")
            continue
        seen_numbers.add(number_key)

        file_id = str(item.get("id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            errors.append(f"{grade} класс: некорректный ID файла {name}")
            continue

        options, correct_index, correct_answer = _answer_options(
            match.group("answer"), file_id
        )
        questions.append(
            Question(
                grade=grade,
                topic="Задания из папки Google Drive",
                question=f"Решите задание №{number} на изображении.",
                options=options,
                correct_index=correct_index,
                solution=f"Правильный ответ: {correct_answer}.",
                image_url=f"https://drive.google.com/thumbnail?id={quote(file_id)}&sz=w1600",
            )
        )

    if errors:
        preview = "; ".join(errors[:5])
        suffix = "…" if len(errors) > 5 else ""
        raise QuestionFormatError(
            "Переименуйте изображения по схеме «номер - правильный ответ»: "
            + preview
            + suffix
        )
    return questions


def parse_extended_drive_index(payload) -> dict[int, list[dict]]:
    """Build second-part task rubrics from each grade's `2 часть` folder."""
    files = payload.get("extendedFiles") if isinstance(payload, dict) else None
    if not isinstance(files, list):
        return {grade: [] for grade in SUPPORTED_GRADES}
    tasks = {grade: [] for grade in SUPPORTED_GRADES}
    errors = []
    seen = set()
    for item in files:
        if not isinstance(item, dict) or item.get("mimeType") not in IMAGE_TYPES:
            continue
        try:
            grade = int(item.get("grade"))
        except (TypeError, ValueError):
            continue
        if grade not in SUPPORTED_GRADES:
            continue
        name = os.path.basename(str(item.get("name") or ""))
        match = FILENAME_PATTERN.match(name)
        if not match:
            errors.append(f"{grade} класс / 2 часть: {name}")
            continue
        number = int(match.group("number"))
        if (grade, number) in seen:
            errors.append(f"{grade} класс / 2 часть: повторяется номер {number}")
            continue
        seen.add((grade, number))
        file_id = str(item.get("id") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            errors.append(f"{grade} класс / 2 часть: некорректный ID {name}")
            continue
        _options, _correct_index, answer = _answer_options(match.group("answer"), file_id)
        exam = "ОГЭ" if grade == 9 else "ЕГЭ" if grade == 11 else "Итоговая контрольная"
        criteria = (
            "Критерии ОГЭ: математически грамотный и завершённый ход решения"
            if grade == 9 else
            "Критерии ЕГЭ для задачи соответствующего типа"
            if grade == 11 else
            "Математические правила, корректность преобразований и полнота решения"
        )
        tasks[grade].append({
            "id": f"drive-extended-{grade}-{file_id}",
            "title": f"{exam} · задание №{number}",
            "question": f"Решите задание №{number}. Приложите развёрнутое решение и запишите ответ.",
            "imageUrl": f"https://drive.google.com/thumbnail?id={quote(file_id)}&sz=w1600",
            "kind": f"{exam}, {grade} класс",
            "maxScore": 2,
            "criteriaSource": criteria,
            "fields": [{
                "id": "answer",
                "label": "Итоговый ответ",
                "hint": "Введите ответ через MathLive",
                "answers": [answer],
                "points": 2,
            }],
        })
    if errors:
        preview = "; ".join(errors[:5])
        raise QuestionFormatError(
            "В папках «2 часть» используйте схему «номер - правильный ответ»: " + preview
        )
    return tasks


def parse_expert_game_index(payload, max_score=2) -> list[dict]:
    """Match `Решения/N - score` with the hidden reveal image `Ответы/N`."""
    solution_files = payload.get("solutions") if isinstance(payload, dict) else None
    answer_files = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(solution_files, list) or not isinstance(answer_files, list):
        raise QuestionFormatError("Папка оценивания должна содержать «Решения» и «Ответы»")
    try:
        max_score = int(max_score)
    except (TypeError, ValueError) as error:
        raise QuestionFormatError("Максимальный балл игры должен быть целым числом") from error
    if not 1 <= max_score <= 10:
        raise QuestionFormatError("Максимальный балл игры должен быть от 1 до 10")

    answers_by_number = {}
    errors = []
    for item in answer_files:
        if not isinstance(item, dict) or item.get("mimeType") not in IMAGE_TYPES:
            continue
        name = os.path.basename(str(item.get("name") or ""))
        match = EXPERT_ANSWER_PATTERN.match(name)
        if not match:
            errors.append(f"Ответы/{name}")
            continue
        number = int(match.group("number"))
        file_id = str(item.get("id") or "").strip()
        if number in answers_by_number:
            errors.append(f"Ответы: повторяется номер {number}")
        elif re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            answers_by_number[number] = file_id
        else:
            errors.append(f"Ответы/{name}: некорректный ID")

    tasks = []
    seen = set()
    for item in solution_files:
        if not isinstance(item, dict) or item.get("mimeType") not in IMAGE_TYPES:
            continue
        name = os.path.basename(str(item.get("name") or ""))
        match = EXPERT_SOLUTION_PATTERN.match(name)
        if not match:
            errors.append(f"Решения/{name}")
            continue
        number = int(match.group("number"))
        expert_score = int(match.group("score"))
        file_id = str(item.get("id") or "").strip()
        if number in seen:
            errors.append(f"Решения: повторяется номер {number}")
            continue
        seen.add(number)
        if expert_score > max_score:
            errors.append(f"Решения/{name}: балл выше максимума {max_score}")
            continue
        if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            errors.append(f"Решения/{name}: некорректный ID")
            continue
        if number not in answers_by_number:
            errors.append(f"Для решения {number} нет файла Ответы/{number}")
            continue
        tasks.append({
            "id": f"expert-work-{number}-{file_id}",
            "number": number,
            "title": f"Работа №{number}",
            "question": "Изучите решение ученика и поставьте балл, как эксперт.",
            "imageUrl": f"https://drive.google.com/thumbnail?id={quote(file_id)}&sz=w2000",
            "answerImageUrl": (
                "https://drive.google.com/thumbnail?id="
                f"{quote(answers_by_number[number])}&sz=w2000"
            ),
            "kind": "Проверка развёрнутого решения",
            "maxScore": max_score,
            "expertScore": expert_score,
            "criteriaSource": "Сравните полноту и корректность решения с критериями экзамена.",
            "fields": [],
        })
    if errors:
        raise QuestionFormatError("Ошибка в папке игры «Ты — эксперт»: " + "; ".join(errors[:8]))
    if not tasks:
        raise QuestionFormatError("В папке «Решения» нет работ по схеме «номер - балл»")
    return sorted(tasks, key=lambda item: item["number"])


def parse_public_folder_html(html: str) -> list[dict]:
    """Read public Drive folder entries from the initial page payload."""
    match = PUBLIC_FOLDER_DATA_PATTERN.search(html)
    if not match:
        raise QuestionFormatError(
            "Google Drive не отдал список файлов. Проверьте общий доступ к папке"
        )
    try:
        # Drive serialises the JSON as a quoted JavaScript string. Replacing the
        # harmless escaped slash avoids Python's invalid-escape warning.
        encoded = match.group(1).replace(r"\/", "/")
        payload = json.loads(ast.literal_eval("'" + encoded + "'"))
    except (SyntaxError, ValueError, json.JSONDecodeError) as error:
        raise QuestionFormatError("Не удалось прочитать публичную папку Google Drive") from error

    entries = payload[0] if isinstance(payload, list) and payload else None
    if not isinstance(entries, list):
        raise QuestionFormatError("Google Drive вернул папку в неизвестном формате")

    result = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 4:
            continue
        file_id, name, mime_type = entry[0], entry[2], entry[3]
        if not isinstance(file_id, str) or not isinstance(name, str) or not isinstance(mime_type, str):
            continue
        result.append({"id": file_id, "name": name, "mimeType": mime_type})
    return result


async def _fetch_complete_public_folder(session, folder_id: str, html: str):
    """Use a public key embedded by Drive to get every item, including pages after 50."""
    api_keys = list(dict.fromkeys(PUBLIC_API_KEY_PATTERN.findall(html)))
    if not api_keys:
        return None

    for api_key in api_keys:
        entries = []
        page_token = ""
        failed = False
        for _page in range(20):
            params = {
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "nextPageToken,files(id,name,mimeType)",
                "pageSize": "1000",
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            async with session.get(DRIVE_FILES_API_URL, params=params) as response:
                if response.status != 200:
                    failed = True
                    break
                try:
                    payload = await response.json(content_type=None)
                except (TypeError, ValueError, json.JSONDecodeError):
                    failed = True
                    break
            files = payload.get("files") if isinstance(payload, dict) else None
            if not isinstance(files, list):
                failed = True
                break
            for item in files:
                if not isinstance(item, dict):
                    continue
                file_id = item.get("id")
                name = item.get("name")
                mime_type = item.get("mimeType")
                if all(isinstance(value, str) for value in (file_id, name, mime_type)):
                    entries.append({"id": file_id, "name": name, "mimeType": mime_type})
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                break
        if not failed:
            return entries
    return None


async def fetch_public_drive_index(session, root_folder_id: str) -> dict:
    """Collect class images from a public Drive folder without Google credentials."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", root_folder_id or ""):
        raise QuestionFormatError("Некорректный ID корневой папки Google Drive")

    async def read_folder(folder_id):
        url = f"https://drive.google.com/drive/folders/{quote(folder_id)}?usp=drive_link"
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
        initial_entries = parse_public_folder_html(html)
        if len(initial_entries) < 50:
            return initial_entries
        complete_entries = await _fetch_complete_public_folder(session, folder_id, html)
        if complete_entries is not None and len(complete_entries) >= len(initial_entries):
            return complete_entries
        return initial_entries

    root_entries = await read_folder(root_folder_id)
    grade_folders = {}
    for entry in root_entries:
        if entry["mimeType"] != FOLDER_MIME_TYPE:
            continue
        grade_match = re.search(r"(?:^|\D)(8|9|10|11)(?:\D|$)", entry["name"])
        if not grade_match:
            continue
        grade = int(grade_match.group(1))
        if grade in grade_folders:
            raise QuestionFormatError(f"В Google Drive найдено несколько папок для {grade} класса")
        grade_folders[grade] = entry["id"]

    missing = sorted(SUPPORTED_GRADES - set(grade_folders))
    if missing:
        raise QuestionFormatError(
            "В Google Drive не найдены папки классов: " + ", ".join(map(str, missing))
        )

    folder_entries = await asyncio.gather(*(
        read_folder(grade_folders[grade]) for grade in sorted(SUPPORTED_GRADES)
    ))
    files = []
    second_part_folders = {}
    for grade, entries in zip(sorted(SUPPORTED_GRADES), folder_entries):
        for entry in entries:
            if entry["mimeType"] in IMAGE_TYPES:
                files.append({**entry, "grade": grade})
            elif entry["mimeType"] == FOLDER_MIME_TYPE:
                folder_name = re.sub(r"[\s_-]+", "", entry["name"].casefold().replace("ё", "е"))
                if folder_name in {"2часть", "часть2", "втораячасть"}:
                    if grade in second_part_folders:
                        raise QuestionFormatError(
                            f"В папке {grade} класса найдено несколько папок «2 часть»"
                        )
                    second_part_folders[grade] = entry["id"]
    if not files:
        raise QuestionFormatError("В папках 8–11 классов не найдено изображений")
    second_entries = await asyncio.gather(*(
        read_folder(second_part_folders[grade]) if grade in second_part_folders else asyncio.sleep(0, result=[])
        for grade in sorted(SUPPORTED_GRADES)
    ))
    extended_files = []
    for grade, entries in zip(sorted(SUPPORTED_GRADES), second_entries):
        extended_files.extend({**entry, "grade": grade} for entry in entries if entry["mimeType"] in IMAGE_TYPES)
    return {"files": files, "extendedFiles": extended_files}


async def fetch_expert_game_index(session, root_folder_id: str) -> dict:
    """Read the public two-folder bank used by the expert-scoring game."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", root_folder_id or ""):
        raise QuestionFormatError("Некорректный ID папки игры оценивания")

    async def read_folder(folder_id):
        url = f"https://drive.google.com/drive/folders/{quote(folder_id)}?usp=drive_link"
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
        initial_entries = parse_public_folder_html(html)
        if len(initial_entries) < 50:
            return initial_entries
        complete_entries = await _fetch_complete_public_folder(session, folder_id, html)
        return complete_entries if complete_entries is not None else initial_entries

    root_entries = await read_folder(root_folder_id)
    folders = {}
    for entry in root_entries:
        if entry.get("mimeType") != FOLDER_MIME_TYPE:
            continue
        normalised = re.sub(r"[\s_-]+", "", str(entry.get("name") or "").casefold().replace("ё", "е"))
        if normalised in {"решения", "ответы"}:
            if normalised in folders:
                raise QuestionFormatError(f"Найдено несколько папок «{entry['name']}»")
            folders[normalised] = entry["id"]
    missing = [name.title() for name in ("решения", "ответы") if name not in folders]
    if missing:
        raise QuestionFormatError("Не найдены папки: " + ", ".join(missing))
    solutions, answers = await asyncio.gather(
        read_folder(folders["решения"]), read_folder(folders["ответы"])
    )
    return {"solutions": solutions, "answers": answers}
