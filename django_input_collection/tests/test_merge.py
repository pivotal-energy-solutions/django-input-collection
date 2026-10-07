"""merge_requests: one question per measure across requests, in a fixed number of queries."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection.merge import load_instruments, merge_requests
from ..models import get_input_model
from . import factories
from .checklists import build_checklist, gate, question
from .test_cross_request_conditions import Cooperative, HideYes


def coop(*requests, cls=Cooperative):
    found = {}
    for request in requests:
        collector = cls(request)
        collector.others = [r for r in requests if r is not request]
        found[request.pk] = collector
    return found


class MergeTests(TestCase):
    def setUp(self):
        self.a = factories.CollectionRequestFactory.create()
        self.b = factories.CollectionRequestFactory.create()
        question(self.a, "only-a", group="Envelope", order=1)
        question(self.a, "shared", group="Envelope", order=2)
        question(self.b, "shared", group="Envelope", order=5)
        question(self.b, "only-b", group="Ducts", order=1)
        question(self.b, "b-first-section", group="Commissioning", order=0)

    def merged(self, *requests, **kwargs):
        requests = requests or (self.a, self.b)
        return merge_requests(requests, collectors=coop(*requests), **kwargs)

    def answer(self, request, measure, data):
        instrument = request.collectioninstrument_set.get(measure_id=measure)
        return factories.CollectedInputFactory.create(
            instrument=instrument, collection_request=request, data=data
        )

    def test_each_measure_once_owned_by_the_first_request(self):
        merged = self.merged()
        self.assertEqual(
            sorted(merged.questions), ["b-first-section", "only-a", "only-b", "shared"]
        )
        self.assertEqual(merged.owner("shared").collection_request_id, self.a.pk)
        self.assertEqual(len(merged.questions["shared"].instruments), 2)
        with self.assertRaises(KeyError):
            merged.owner("nowhere")

    def test_a_pluggable_owner(self):
        seen = []

        def last(measure_id, instruments, answer):
            seen.append((measure_id, answer))
            return instruments[-1]

        self.answer(self.b, "shared", "yes")
        merged = self.merged(owner=last)
        self.assertEqual(merged.owner("shared").collection_request_id, self.b.pk)
        self.assertEqual(merged.questions["shared"].section, "Envelope")
        self.assertIn(("shared", merged.answers["shared"]), seen)

    def test_section_order_first_request_then_later_only_sections(self):
        merged = self.merged()
        self.assertEqual([s.name for s in merged.sections], ["Envelope", "Commissioning", "Ducts"])
        self.assertEqual([s.order for s in merged.sections], [0, 1, 2])
        envelope = [q.measure_id for q in merged.sections[0].questions]
        self.assertEqual(envelope, ["only-a", "shared"])

    def test_reversed_requests_reorder_sections(self):
        merged = self.merged(self.b, self.a)
        self.assertEqual([s.name for s in merged.sections], ["Commissioning", "Ducts", "Envelope"])
        envelope = [q.measure_id for q in merged.sections[2].questions]
        self.assertEqual(envelope, ["shared", "only-a"])  # B's shared owns its B position

    def test_ungrouped_is_general_and_comes_first(self):
        factories.CollectionInstrumentFactory.create(
            collection_request=self.a,
            measure=factories.MeasureFactory.create(id="loose"),
            group=None,
            order=99,
        )
        self.assertEqual(self.merged().sections[0].name, "General")

    def test_a_section_whose_questions_moved_away_is_dropped(self):
        question(self.b, "b-moved", group="Attic", order=0)
        question(self.a, "b-moved", group="Envelope", order=3)  # A owns it: Attic is empty
        merged = self.merged()
        self.assertNotIn("Attic", [s.name for s in merged.sections])
        self.assertEqual(merged.questions["b-moved"].section, "Envelope")

    def test_newest_answer_per_measure_across_requests(self):
        self.answer(self.a, "shared", "old")
        self.answer(self.b, "shared", "new")
        self.assertEqual(self.merged().answers["shared"].data, "new")
        self.assertEqual(self.merged().questions["shared"].answer.data, "new")

    def test_inputs_override(self):
        old = self.answer(self.a, "shared", "old")
        self.answer(self.b, "shared", "new")
        inputs = get_input_model().objects.filter(pk=old.pk)
        self.assertEqual(self.merged(inputs=inputs).answers["shared"].data, "old")

    def test_visible_if_any_request_shows_it(self):
        shared_b = self.b.collectioninstrument_set.get(measure_id="shared")
        gate(shared_b, "only-b")  # hidden on B (only-b unanswered); ungated on A
        visibility = self.merged().evaluate()
        self.assertTrue(visibility["shared"])
        self.assertFalse(self.merged(self.b).evaluate()["shared"])

    def test_conditions_read_answers_from_other_requests(self):
        only_a = self.a.collectioninstrument_set.get(measure_id="only-a")
        gate(only_a, "only-b")  # only B asks only-b
        self.assertFalse(self.merged().evaluate()["only-a"])
        self.answer(self.b, "only-b", "yes")
        self.assertTrue(self.merged().evaluate()["only-a"])

    def test_condition_inputs_feed_the_index(self):
        only_a = self.a.collectioninstrument_set.get(measure_id="only-a")
        gate(only_a, "only-b")
        self.answer(self.b, "only-b", "yes")
        hidden = get_input_model().objects.none()
        self.assertFalse(self.merged(condition_inputs=hidden).evaluate()["only-a"])

    def test_filtering_collectors_without_condition_inputs_stay_correct(self):
        only_a = self.a.collectioninstrument_set.get(measure_id="only-a")
        gate(only_a, "only-b")
        self.answer(self.b, "only-b", "yes")
        requests = (self.a, self.b)
        merged = merge_requests(requests, collectors=coop(*requests, cls=HideYes))
        self.assertFalse(merged.evaluate()["only-a"])  # HideYes hides the "yes"

    def test_evaluate_a_subset(self):
        self.assertEqual(self.merged().evaluate(measures=["only-a"]), {"only-a": True})

    def test_none_when_every_evaluation_raised(self):
        class Raises(Cooperative):
            __noregister__ = True

            def is_instrument_allowed(self, instrument, **kwargs):
                raise RuntimeError("broken")

        requests = (self.a, self.b)
        merged = merge_requests(requests, collectors=coop(*requests, cls=Raises))
        self.assertIsNone(merged.evaluate()["shared"])

    def test_dependents_are_transitive(self):
        c1 = self.b.collectioninstrument_set.get(measure_id="only-b")
        c2 = self.a.collectioninstrument_set.get(measure_id="only-a")
        gate(c1, "shared")
        gate(c2, "only-b")
        self.assertEqual(sorted(self.merged().dependents("shared")), ["only-a", "only-b"])
        self.assertEqual(self.merged().dependents("only-a"), [])

    def test_dependents_by_instrument_pk(self):
        shared_a = self.a.collectioninstrument_set.get(measure_id="shared")
        only_a = self.a.collectioninstrument_set.get(measure_id="only-a")
        gate(only_a, str(shared_a.pk))
        self.assertEqual(self.merged().dependents("shared"), ["only-a"])

    def test_progress(self):
        merged = self.merged()
        progress = merged.progress(merged.evaluate())
        self.assertEqual(progress["total"], 4)
        self.assertEqual(progress["visible"], 4)
        self.assertEqual(progress["answered"], 0)

    def test_progress_counts_required_by_owner(self):
        required = factories.ResponsePolicyFactory.create(nickname="required", required=True)
        self.a.collectioninstrument_set.filter(measure_id="shared").update(response_policy=required)
        self.answer(self.b, "shared", "yes")
        merged = self.merged()
        progress = merged.progress(merged.evaluate())
        self.assertEqual(progress["required_total"], 1)
        self.assertEqual(progress["required_answered"], 1)
        self.assertEqual(progress["answered"], 1)


class MergeQueryTests(TestCase):
    def requests(self, size, count):
        return [build_checklist(size, prefix=f"r{n}-{size}") for n in range(count)]

    def count(self, size, count=2):
        requests = self.requests(size, count)
        collectors_ = coop(*requests)
        with CaptureQueriesContext(connection) as queries:
            merged = merge_requests(requests, collectors=collectors_)
            merged.progress(merged.evaluate())
        return len(queries)

    def test_queries_do_not_grow_with_instruments(self):
        # 1 instruments + 6 prefetches (bound responses, suggested responses, conditions, groups,
        # cases, child groups; no child groups here so their cases aren't fetched) + 1 answers,
        # reused for the index. Conditions: 0 queries.
        self.assertEqual(self.count(3), self.count(9))
        self.assertEqual(self.count(3), MEASURED_TWO)

    def test_queries_do_not_grow_with_instruments_across_three_requests(self):
        self.assertEqual(self.count(3, 3), self.count(9, 3))
        self.assertEqual(self.count(3, 3), MEASURED_TWO)

    def test_dependents_and_evaluate_subset_are_free(self):
        requests = self.requests(3, 2)
        merged = merge_requests(requests, collectors=coop(*requests))
        with self.assertNumQueries(0):
            merged.dependents("r0-3-gate")
            merged.evaluate(measures=["r0-3-0", "r1-3-1"])
            merged.evaluate()

    def test_given_instruments_and_inputs_skip_those_queries(self):
        requests = self.requests(3, 2)
        instruments = load_instruments(requests)
        inputs = get_input_model().objects.filter(collection_request__in=requests)
        rows = list(inputs)
        collectors_ = coop(*requests)
        with self.assertNumQueries(1):  # inputs is a queryset: one read, reused for the index
            merged = merge_requests(
                requests, collectors=collectors_, instruments=instruments, inputs=inputs
            )
            merged.evaluate()
        self.assertEqual(len(merged.answers), len(rows))


MEASURED_TWO = 8
