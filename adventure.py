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


FORMULA_CHALLENGES = {
    "rectangle-area": {
        "prompt": "Площадь прямоугольника",
        "hint": "Выберите формулу через стороны a и b.",
        "options": [r"S=ab", r"S=2(a+b)", r"S=\frac{ah}{2}", r"S=a^2+b^2"],
        "correct": 0,
    },
    "triangle-height": {
        "prompt": "Площадь треугольника через основание и высоту",
        "hint": "Основание — a, проведённая к нему высота — h.",
        "options": [r"S=ah", r"S=\frac{ah}{2}", r"S=\frac{a+h}{2}", r"S=a^2+h^2"],
        "correct": 1,
    },
    "parallelogram-area": {
        "prompt": "Площадь параллелограмма",
        "hint": "Сторона a и проведённая к ней высота h.",
        "options": [r"S=\frac{ah}{2}", r"S=2(a+h)", r"S=ah", r"S=a+h"],
        "correct": 2,
    },
    "trapezoid-area": {
        "prompt": "Площадь трапеции",
        "hint": "Основания — a и b, высота — h.",
        "options": [r"S=(a+b)h", r"S=\frac{(a+b)h}{2}", r"S=\frac{ab}{2}", r"S=(a-b)h"],
        "correct": 1,
    },
    "rhombus-area": {
        "prompt": "Площадь ромба через диагонали",
        "hint": "Диагонали обозначены d₁ и d₂.",
        "options": [r"S=d_1+d_2", r"S=2d_1d_2", r"S=\frac{d_1d_2}{2}", r"S=(d_1-d_2)^2"],
        "correct": 2,
    },
    "cosine-theorem": {
        "prompt": "Теорема косинусов",
        "hint": "Сторона c лежит напротив угла C.",
        "options": [r"c^2=a^2+b^2-2ab\cos C", r"c^2=a^2+b^2", r"\frac{a}{\sin A}=\frac{b}{\sin B}", r"S=\frac{ab\sin C}{2}"],
        "correct": 0,
    },
    "sine-theorem": {
        "prompt": "Теорема синусов",
        "hint": "R — радиус описанной окружности.",
        "options": [r"a^2=b^2+c^2-2bc\cos A", r"\frac{a}{\sin A}=\frac{b}{\sin B}=\frac{c}{\sin C}=2R", r"S=pr", r"a+b+c=2R"],
        "correct": 1,
    },
    "triangle-sine-area": {
        "prompt": "Площадь треугольника через две стороны и угол",
        "hint": "Угол C заключён между сторонами a и b.",
        "options": [r"S=ab\sin C", r"S=\frac{ab\cos C}{2}", r"S=\frac{ab\sin C}{2}", r"S=\frac{a+b}{2}\sin C"],
        "correct": 2,
    },
    "heron": {
        "prompt": "Формула Герона",
        "hint": "p — полупериметр треугольника.",
        "options": [r"S=\sqrt{p(p-a)(p-b)(p-c)}", r"S=p(p-a)(p-b)(p-c)", r"S=\frac{abc}{2p}", r"S=pr^2"],
        "correct": 0,
    },
    "circle-area": {
        "prompt": "Площадь круга",
        "hint": "R — радиус круга.",
        "options": [r"S=2\pi R", r"S=\pi R^2", r"S=\frac{\pi R^2}{2}", r"S=4\pi R^2"],
        "correct": 1,
    },
    "sector-area": {
        "prompt": "Площадь сектора круга",
        "hint": "Центральный угол α задан в градусах.",
        "options": [r"S=\frac{\alpha\pi R^2}{360^\circ}", r"S=\frac{\alpha\pi R}{180^\circ}", r"S=\alpha\pi R^2", r"S=\frac{2\pi R}{\alpha}"],
        "correct": 0,
    },
    "arithmetic-progression": {
        "prompt": "n-й член арифметической прогрессии",
        "hint": "a₁ — первый член, d — разность.",
        "options": [r"a_n=a_1d^{n-1}", r"a_n=a_1+d(n-1)", r"a_n=\frac{a_1+a_n}{2}", r"a_n=a_1+dn"],
        "correct": 1,
    },
    "trig-identity": {
        "prompt": "Основное тригонометрическое тождество",
        "hint": "Выберите равенство, верное для любого допустимого x.",
        "options": [r"\sin x+\cos x=1", r"\sin^2x-\cos^2x=1", r"\sin^2x+\cos^2x=1", r"\tan x\cdot\cos x=1"],
        "correct": 2,
    },
    "power-derivative": {
        "prompt": "Производная степенной функции",
        "hint": "Найдите общую формулу для (xⁿ)′.",
        "options": [r"(x^n)'=nx^{n-1}", r"(x^n)'=x^{n-1}", r"(x^n)'=n^x", r"(x^n)'=(n-1)x^n"],
        "correct": 0,
    },
    "cylinder-volume": {
        "prompt": "Объём цилиндра",
        "hint": "R — радиус основания, h — высота.",
        "options": [r"V=2\pi Rh", r"V=\pi R^2h", r"V=\frac{\pi R^2h}{3}", r"V=\pi Rh^2"],
        "correct": 1,
    },
    "cone-volume": {
        "prompt": "Объём конуса",
        "hint": "R — радиус основания, h — высота.",
        "options": [r"V=\pi R^2h", r"V=\frac{\pi Rh}{3}", r"V=\frac{\pi R^2h}{3}", r"V=\pi Rl"],
        "correct": 2,
    },
    "sphere-volume": {
        "prompt": "Объём шара",
        "hint": "R — радиус шара.",
        "options": [r"V=4\pi R^2", r"V=\frac{4\pi R^3}{3}", r"V=\pi R^3", r"V=\frac{\pi R^3}{3}"],
        "correct": 1,
    },
}


FORMULA_POOLS = {
    8: ["rectangle-area", "triangle-height", "parallelogram-area", "trapezoid-area", "rhombus-area"],
    9: ["triangle-height", "trapezoid-area", "cosine-theorem", "sine-theorem", "triangle-sine-area", "heron", "circle-area"],
    10: ["cosine-theorem", "sine-theorem", "triangle-sine-area", "heron", "sector-area", "arithmetic-progression", "trig-identity"],
    11: ["cosine-theorem", "sine-theorem", "triangle-sine-area", "sector-area", "trig-identity", "power-derivative", "cylinder-volume", "cone-volume", "sphere-volume"],
}

FORMULA_ROUND_SIZE = 4


def build_formula_round(grade, seed=None):
    """Build a stable, duplicate-free set of formula associations for one run."""
    grade = int(grade)
    generator = random.Random(seed)
    challenge_ids = generator.sample(FORMULA_POOLS[grade], FORMULA_ROUND_SIZE)
    result = []
    for challenge_id in challenge_ids:
        source = FORMULA_CHALLENGES[challenge_id]
        option_rows = [
            {"id": f"{challenge_id}:{index}", "formula": formula}
            for index, formula in enumerate(source["options"])
        ]
        generator.shuffle(option_rows)
        result.append({
            "id": challenge_id,
            "prompt": source["prompt"],
            "hint": source["hint"],
            "options": option_rows,
            "correctOptionId": f"{challenge_id}:{source['correct']}",
        })
    return result


def ensure_formula_round(session):
    """Migrate unfinished crystal sessions and initialise formula progress."""
    if session.get("stage") == "crystals":
        session["stage"] = "formula"
    if not session.get("formula_round"):
        session["formula_round"] = build_formula_round(
            int(session["grade"]), seed=str(session.get("id") or session.get("attempt_key") or "")
        )
    session.setdefault("formula_index", 0)
    session.setdefault("formula_score", 0)
    session.setdefault("formula_attempts", 0)
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


def new_session(user_id, grade, attempt_key, task=None):
    session = {
        "id": uuid.uuid4().hex,
        "user_id": str(user_id),
        "grade": int(grade),
        "attempt_key": str(attempt_key or uuid.uuid4().hex),
        "stage": "formula",
        "status": "active",
        "task": task or ADVENTURE_TASKS[int(grade)],
    }
    return ensure_formula_round(session)
