import json
from pathlib import Path
import random
import re
import uuid


ADVENTURE_TASKS = {
    8: {
        "id": "control-8-quadratic",
        "title": "Итоговая контрольная · квадратное уравнение",
        "question": "Решите уравнение: $x^2-5x+6=0$. Запишите основные шаги и ответ.",
        "kind": "Итоговая контрольная, 8 класс",
        "maxScore": 2,
        "criteriaSource": "Математические правила и полнота решения",
        "fields": [
            {"id": "factor", "label": "Разложение на множители", "hint": "Например: (x-2)(x-3)=0", "answers": ["(x-2)(x-3)=0", "(x-3)(x-2)=0"], "points": 1},
            {"id": "answer", "label": "Ответ", "hint": "Введите оба корня", "answers": ["2;3", "3;2", "2,3", "3,2"], "points": 1},
        ],
    },
    9: {
        "id": "oge-9-equation",
        "title": "ОГЭ · задание с развёрнутым ответом",
        "question": "Решите уравнение: $x^2-7x+12=0$. Покажите ход решения и запишите ответ.",
        "kind": "ОГЭ, развёрнутый ответ",
        "maxScore": 2,
        "criteriaSource": "Методические рекомендации ОГЭ: ход решения, завершённость, математическая грамотность",
        "fields": [
            {"id": "step", "label": "Ключевой шаг", "hint": "Разложение или вычисление дискриминанта", "answers": ["(x-3)(x-4)=0", "(x-4)(x-3)=0", "d=1", "D=1"], "points": 1},
            {"id": "answer", "label": "Ответ", "hint": "Введите оба корня", "answers": ["3;4", "4;3", "3,4", "4,3"], "points": 1},
        ],
    },
    10: {
        "id": "control-10-inequality",
        "title": "Итоговая контрольная · неравенство",
        "question": r"Решите неравенство: $x^2-5x+6\leq0$. Укажите нули и итоговый промежуток.",
        "kind": "Итоговая контрольная, 10 класс",
        "maxScore": 2,
        "criteriaSource": "Математические правила и полнота решения",
        "fields": [
            {"id": "zeros", "label": "Нули выражения", "hint": "Введите два числа", "answers": ["2;3", "3;2", "2,3", "3,2"], "points": 1},
            {"id": "answer", "label": "Ответ", "hint": "Введите промежуток", "answers": ["[2;3]", "[2,3]", "2<=x<=3", "2≤x≤3"], "points": 1},
        ],
    },
    11: {
        "id": "ege-11-logarithm",
        "title": "ЕГЭ · уравнение с обоснованием",
        "question": r"Решите уравнение: $\log_2(x-1)+\log_2(x-3)=3$. Укажите ОДЗ, преобразование и ответ.",
        "kind": "ЕГЭ, развёрнутый ответ",
        "maxScore": 2,
        "criteriaSource": "Критерии ЕГЭ для соответствующего типа задания: корректность преобразований, ограничения и ответ",
        "fields": [
            {"id": "domain", "label": "Область допустимых значений", "hint": "Введите условие на x", "answers": ["x>3", "3<x"], "points": 1},
            {"id": "answer", "label": "Ответ", "hint": "Введите корень", "answers": ["5", "x=5"], "points": 1},
        ],
    },
}


FORMULA_SOURCE_PATH = Path(__file__).with_name("formula_tower.json")
FORMULA_ROUND_SIZE = 10
FORMULA_MAX_MISTAKES = 4
FORMULA_REWARD_PER_CORRECT = 50
FORMULA_ROUND_VERSION = 3


with FORMULA_SOURCE_PATH.open(encoding="utf-8") as formula_source:
    FORMULA_CHALLENGES_BY_GRADE = {
        int(grade): challenges
        for grade, challenges in json.load(formula_source).items()
    }

# Flattened index is kept for diagnostics and tests.
FORMULA_CHALLENGES = {
    challenge["id"]: challenge
    for challenges in FORMULA_CHALLENGES_BY_GRADE.values()
    for challenge in challenges
}


def build_formula_round(grade, seed=None):
    # Build ten unique, grade-specific associations from the supplied formula file.
    grade = int(grade)
    if grade not in FORMULA_CHALLENGES_BY_GRADE:
        raise ValueError("Некорректный класс")
    generator = random.Random(seed)
    selected = generator.sample(FORMULA_CHALLENGES_BY_GRADE[grade], FORMULA_ROUND_SIZE)
    result = []
    for source in selected:
        challenge_id = source["id"]
        option_rows = [{
            "id": "{}:correct".format(challenge_id),
            "text": source["formula"],
        }]
        option_rows.extend({
            "id": "{}:wrong:{}".format(challenge_id, index),
            "text": option_text,
        } for index, option_text in enumerate(source["wrongInterpretations"], start=1))
        generator.shuffle(option_rows)
        result.append({
            "id": challenge_id,
            "prompt": source["title"],
            "formula": "",
            "hint": "Условия: {}".format(source["conditions"])
                if source.get("conditions") else "Выберите правильную формулу.",
            "options": option_rows,
            "correctOptionId": "{}:correct".format(challenge_id),
        })
    return result


def ensure_formula_round(session):
    # Migrate old tower sessions and initialise the ten-question round.
    if session.get("stage") == "crystals":
        session["stage"] = "formula"
    if (
        session.get("formula_round_version") != FORMULA_ROUND_VERSION
        or not session.get("formula_round")
    ):
        session["formula_round"] = build_formula_round(
            int(session["grade"]), seed=str(session.get("id") or session.get("attempt_key") or "")
        )
        session["formula_round_version"] = FORMULA_ROUND_VERSION
        session["formula_index"] = 0
        session["formula_score"] = 0
        session["formula_attempts"] = 0
        session["formula_errors"] = 0
        session.pop("formula_feedback", None)
    session.setdefault("formula_index", 0)
    session.setdefault("formula_score", 0)
    session.setdefault("formula_attempts", 0)
    session.setdefault("formula_errors", 0)
    return session


def public_formula_state(session):
    ensure_formula_round(session)
    index = int(session.get("formula_index") or 0)
    formula_round = session["formula_round"]
    challenge = None
    if index < len(formula_round):
        challenge = {
            key: value for key, value in formula_round[index].items()
            if key != "correctOptionId"
        }
    return {
        "index": index,
        "total": len(formula_round),
        "score": int(session.get("formula_score") or 0),
        "attempts": int(session.get("formula_attempts") or 0),
        "mistakes": int(session.get("formula_errors") or 0),
        "maxMistakes": FORMULA_MAX_MISTAKES,
        "rewardPerCorrect": FORMULA_REWARD_PER_CORRECT,
        "challenge": challenge,
        "feedback": session.get("formula_feedback"),
    }


def _normalise_math(value):
    value = str(value or "").strip().lower().replace("−", "-").replace("–", "-")
    value = value.replace("\\leq", "<=").replace("\\geq", ">=").replace("\\cdot", "*")
    value = value.replace("\\left", "").replace("\\right", "").replace(" ", "")
    value = value.replace("{", "").replace("}", "").replace("$", "")
    return value


def grade_solution(task, answers, explanation=""):
    results = []
    score = 0
    for field in task["fields"]:
        value = str((answers or {}).get(field["id"]) or "").strip()
        correct = bool(value) and _normalise_math(value) in {
            _normalise_math(answer) for answer in field["answers"]
        }
        earned = int(field["points"]) if correct else 0
        score += earned
        results.append({
            "id": field["id"],
            "label": field["label"],
            "correct": correct,
            "earned": earned,
            "max": int(field["points"]),
        })

    has_reasoning = len(re.sub(r"\s+", "", str(explanation or ""))) >= 12
    if score == task["maxScore"] and not has_reasoning:
        score = max(1, score - 1)
    if score == task["maxScore"]:
        verdict = "Решение завершено и математически корректно."
    elif score == 1:
        verdict = "Ход решения частично верен, но есть недочёт или решение не доведено до конца."
    else:
        verdict = "Есть существенная ошибка или недостаточно связного решения для начисления балла."
    return {"score": score, "maxScore": task["maxScore"], "criteria": results, "verdict": verdict}


def public_task(task_or_grade):
    task = task_or_grade if isinstance(task_or_grade, dict) else ADVENTURE_TASKS[int(task_or_grade)]
    return {
        key: value for key, value in task.items() if key != "fields"
    } | {
        "fields": [{key: value for key, value in field.items() if key != "answers"} for field in task["fields"]]
    }


def new_session(user_id, grade, attempt_key, task=None, game="tower"):
    game = str(game or "tower")
    if game not in {"tower", "second_part"}:
        raise ValueError("Unknown adventure game")
    session = {
        "id": uuid.uuid4().hex,
        "user_id": str(user_id),
        "grade": int(grade),
        "attempt_key": str(attempt_key or uuid.uuid4().hex),
        "game": game,
        "stage": "formula" if game == "tower" else "solution",
        "status": "active",
        "task": task or ADVENTURE_TASKS[int(grade)],
    }
    return ensure_formula_round(session) if game == "tower" else session
