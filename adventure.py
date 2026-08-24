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


def new_session(user_id, grade, attempt_key, task=None):
    return {
        "id": uuid.uuid4().hex,
        "user_id": str(user_id),
        "grade": int(grade),
        "attempt_key": str(attempt_key or uuid.uuid4().hex),
        "stage": "crystals",
        "crystals": [],
        "status": "active",
        "task": task or ADVENTURE_TASKS[int(grade)],
    }
