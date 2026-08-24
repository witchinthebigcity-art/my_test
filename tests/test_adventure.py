import os
import tempfile
import unittest

from adventure import ADVENTURE_TASKS, grade_solution
from community import CommunityStore


class AdventureRubricTests(unittest.TestCase):
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

    async def test_adventure_resumes_and_completes_after_three_crystals(self):
        session = await self.store.start_adventure(self.user, 8, "training-1")
        resumed = await self.store.get_adventure(self.user, 8)
        self.assertTrue(resumed["active"])
        self.assertEqual(resumed["session"]["id"], session["id"])
        for crystal in ("logic", "formula", "focus"):
            session = await self.store.collect_adventure_crystal(self.user, session["id"], crystal)
        self.assertEqual(session["stage"], "solution")
        completed = await self.store.submit_adventure(self.user, session["id"], {
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
        session = await self.store.start_adventure(self.user, 9, "training-2", task=task)
        self.assertEqual(session["task"]["title"], "Пользовательская задача")
        self.assertNotIn("answers", session["task"]["fields"][0])
