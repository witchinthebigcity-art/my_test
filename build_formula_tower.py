#!/usr/bin/env python3
"""Convert the teacher's compact formula catalogue into tower JSON."""

import argparse
import json
import re
from pathlib import Path


GRADE_HEADING = re.compile(r"^(8|9|10|11) КЛАСС$")


def _is_section_heading(value):
    return bool(re.fullmatch(r"[А-ЯЁ ]{3,}", value))


def _read_value(lines, index, stop_labels):
    values = []
    while index < len(lines):
        if lines[index] in stop_labels:
            break
        if index + 1 < len(lines) and lines[index + 1] == "Правильно:":
            break
        if GRADE_HEADING.match(lines[index]):
            break
        if _is_section_heading(lines[index]):
            break
        if lines[index] and not lines[index].startswith("="):
            values.append(lines[index])
        index += 1
    return "\n".join(values).strip(), index


def parse_formula_catalogue(text):
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    result = {"8": [], "9": [], "10": [], "11": []}
    grade = None
    index = 0

    while index < len(lines):
        heading = GRADE_HEADING.match(lines[index])
        if heading:
            grade = heading.group(1)
            index += 1
            continue

        if grade and index + 1 < len(lines) and lines[index + 1] == "Правильно:":
            title = lines[index]
            index += 2
            correct, index = _read_value(lines, index, {"Условия:", "Ошибка 1:"})
            conditions = ""
            if index < len(lines) and lines[index] == "Условия:":
                index += 1
                conditions, index = _read_value(lines, index, {"Ошибка 1:"})
            if index >= len(lines) or lines[index] != "Ошибка 1:":
                raise ValueError(f"Для «{title}» не найдена первая ошибка")
            index += 1
            wrong_one, index = _read_value(lines, index, {"Ошибка 2:"})
            if index >= len(lines) or lines[index] != "Ошибка 2:":
                raise ValueError(f"Для «{title}» не найдена вторая ошибка")
            index += 1
            wrong_two, index = _read_value(lines, index, set())

            if not all((title, correct, wrong_one, wrong_two)):
                raise ValueError(f"Неполная карточка «{title}»")
            row = {
                "id": f"g{grade}-{len(result[grade]) + 1:02d}",
                "title": title,
                "formula": correct,
                # Kept for backwards-compatible diagnostics; the game now uses
                # the correct formula itself as the correct answer option.
                "correctInterpretation": correct,
                "wrongInterpretations": [wrong_one, wrong_two],
            }
            if conditions:
                row["conditions"] = conditions
            result[grade].append(row)
            continue
        index += 1

    expected = {"8": 25, "9": 16, "10": 38, "11": 32}
    actual = {grade_key: len(rows) for grade_key, rows in result.items()}
    if actual != expected:
        raise ValueError(f"Неожиданное число карточек: {actual}; ожидалось: {expected}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=Path("formula_tower.json"))
    arguments = parser.parse_args()
    catalogue = parse_formula_catalogue(arguments.source.read_text(encoding="utf-8"))
    arguments.output.write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Формулы обновлены:", ", ".join(
        f"{grade} класс — {len(rows)}" for grade, rows in catalogue.items()
    ))


if __name__ == "__main__":
    main()
