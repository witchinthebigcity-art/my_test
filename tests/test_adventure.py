import os
import tempfile
import unittest

from adventure import ADVENTURE_TASKS, FORMULA_CHALLENGES, build_formula_round, grade_solution
from community import CommunityStore


class AdventureRubricTests(unittest.TestCase):
    def test_formula_round_has_four_unique_grade_appropriate_challenges(self):
        formula_round = build_formula_round(9, seed="stable")
        self.assertEqual(len(formula_round), 4)
        self.assertEqual(len({item["id"] for item in formula_round}), 4)
        self.assertTrue(all(len(item["options"]) == 4 for item in formula_round))
        self.assertTrue(all(item["correctOptionId"] in {option["id"] for option in item["options"]} for item in formula_round))

    def test_every_formula_challenge_has_exactly_one_valid_answer_reference(self):
        for challenge_id, challenge in FORMULA_CHALLENGES.items():
            self.assertEqual(len(challenge["options"]), 4, challenge_id)
            self.assertIn(challenge["correct"], range(4), challenge_id)

    def test_full_score_requires_correct_fields_and_reasoning(self):
        task = ADVENTURE_TASKS[9]
        full = grade_solution(task, {"step": "D=1", "answer": "3;4"}, "Вычислим дискриминант и найдём оба корня.")
        self.assertEqual(full["score"], 2)
        answer_only = grade_solution(task, {"step": "D=1", "answer": "3;4"}, "")
        self.assertEqual(answer_only["score"], 1)


class AdventureStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = CommunityStore(os.path.join(self.directory.name, "community.json"))
        self.user = {"id": 77, "first_name": "Ученик", "username": "student"}

    async def asyncTearDown(self):
        self.directory.cleanup()

    async def test_adventure_resumes_and_completes_after_formula_tower(self):
        session = await self.store.start_adventure(self.user, 8, "training-1")
        resumed = await self.store.get_adventure(self.user, 8)
        self.assertTrue(resumed["active"])
        self.assertEqual(resumed["session"]["id"], session["id"])
        self.assertEqual(session["stage"], "formula")
        self.assertNotIn("correctOptionId", session["formula"]["challenge"])
        for _index in range(4):
            stored = self.store._load()["adventures"][session["id"]]
            current = stored["formula_round"][stored["formula_index"]]
            session = await self.store.answer_adventure_formula(
                self.user, session["id"], current["correctOptionId"]
            )
        self.assertEqual(session["stage"], "complete")
        self.assertEqual(session["game"], "tower")
        self.assertEqual(session["result"]["score"], 4)

        solution = await self.store.start_adventure(
            self.user, 8, "training-1", game="second_part"
        )
        self.assertEqual(solution["stage"], "solution")
        completed = await self.store.submit_adventure(self.user, solution["id"], {
            "answers": {"factor": "(x-2)(x-3)=0", "answer": "2;3"},
            "explanation": "Разложим квадратный трёхчлен на множители и приравняем каждый к нулю.",
        })
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(completed["result"]["score"], 2)
        self.assertFalse((await self.store.get_adventure(self.user, 8))["active"])
        history = await self.store.adventure_history(self.user, 8)
        self.assertEqual(history[0]["topics"], ["Вторая часть"])
        self.assertEqual(history[0]["correct"], 2)
        used = await self.store.used_adventure_task_ids(self.user, 8, "training-1")
        self.assertIn(ADVENTURE_TASKS[8]["id"], used)

    async def test_dynamic_drive_task_is_snapshotted_in_session(self):
        task = {
            "id": "drive-extended",
            "title": "Пользовательская задача",
            "question": "Решите задачу с изображения.",
            "imageUrl": "https://example.com/task.png",
            "kind": "ОГЭ",
            "maxScore": 2,
            "criteriaSource": "Критерии ОГЭ",
            "fields": [{"id": "answer", "label": "Ответ", "hint": "", "answers": ["42"], "points": 2}],
        }
        session = await self.store.start_adventure(self.user, 9, "training-2", task=task, game="second_part")
        self.assertEqual(session["task"]["title"], "Пользовательская задача")
        self.assertNotIn("answers", session["task"]["fields"][0])
