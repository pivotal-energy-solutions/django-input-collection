"""The merged checklist keyed by question key: measure_id for every unrepeated question."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.test import TestCase

from ..collection.merge import merge_requests
from ..collection.merged_checklist import MergedQuestion
from ..schema.merged import merged_checklist_payload
from .checklists import build_checklist
from .repeats import answer
from .test_merge import coop


class MergeKeyTests(TestCase):
    def setUp(self):
        self.request = build_checklist(2)  # q-gate "yes"; q-0 shown on yes, q-1 on no

    def merged(self):
        return merge_requests([self.request], collectors=coop(self.request))

    def test_every_question_is_keyed_by_its_measure(self):
        merged = self.merged()
        self.assertEqual(sorted(merged.questions), ["q-0", "q-1", "q-gate"])
        for key, question in merged.questions.items():
            self.assertEqual((question.key, question.measure_id), (key, key))
            self.assertIsNone(question.repeat)

    def test_evaluate_takes_keys(self):
        merged = self.merged()
        self.assertEqual(merged.evaluate(keys=["q-0"]), {"q-0": True})
        self.assertEqual(merged.evaluate(["q-1"]), {"q-1": False})
        self.assertEqual(merged.evaluate(measures=["q-0"]), {"q-0": True})  # pre-key name

    def test_answers_are_newest_per_measure_and_copy(self):
        gate_instrument = self.request.collectioninstrument_set.get(measure_id="q-gate")
        answer(gate_instrument, "no", repeat_index=1)  # a stray copy row: its own key
        merged = self.merged()
        self.assertEqual(merged.answers["q-gate"].data, "yes")
        self.assertEqual(merged.answers["q-gate#1"].data, "no")
        self.assertEqual(merged.questions["q-gate"].answer.data, "yes")
        self.assertEqual([row.data for row in merged.questions["q-gate"].answers], ["yes"])
        self.assertTrue(merged.evaluate()["q-0"])  # the gate reads the unrepeated "yes"
        self.assertEqual(merged.owner("q-gate"), gate_instrument)

    def test_the_payload_carries_key_and_no_repeat(self):
        payload = merged_checklist_payload(self.merged(), collectors=coop(self.request))
        questions = [q for s in payload["sections"] for q in s["questions"]]
        self.assertEqual(len(questions), 3)
        for question in questions:
            self.assertEqual(question["key"], question["measure_id"])
            self.assertIsNone(question["repeat"])

    def test_a_question_built_by_position_keys_itself(self):
        question = MergedQuestion("m", None, (), "General")
        self.assertEqual(question.key, "m")
        self.assertIsNone(question.repeat)
