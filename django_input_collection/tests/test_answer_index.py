"""AnswerIndex answers instrument: conditions without queries, exactly as the database path does."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection import collectors
from ..collection.answer_index import AnswerIndex
from ..collection.merge import load_instruments
from ..collection.resolvers import read_pass
from ..models import CollectedInput
from . import factories
from .checklists import build_checklist, gate, question
from .test_cross_request_conditions import Cooperative


class HideYes(collectors.Collector):
    """Stands in for a role filter: this collector never sees "yes" answers."""

    __noregister__ = True

    def filter_condition_inputs(self, queryset):
        return queryset.exclude(data="yes")


def visibility(collection_request, collector, index=None):
    instruments = load_instruments([collection_request])
    with read_pass(index=index):
        return {i.measure_id: collector.is_instrument_allowed(i) for i in instruments}


def condition_inputs(collector):
    """What InstrumentResolver would read for ``collector``: the index's input contract."""
    return collector.filter_condition_inputs(
        CollectedInput.objects.filter_for_context(**collector.context)
    )


class AnswerIndexTests(TestCase):
    def test_same_answers_as_the_database(self):
        request = build_checklist(6)
        collector = collectors.Collector(request)
        index = AnswerIndex(load_instruments([request]), CollectedInput.objects.all())
        self.assertEqual(visibility(request, collector), visibility(request, collector, index))

    def test_no_condition_queries_under_an_index(self):
        request = build_checklist(6)
        collector = collectors.Collector(request)
        instruments = load_instruments([request])
        index = AnswerIndex(instruments, list(CollectedInput.objects.all()))
        with CaptureQueriesContext(connection) as queries, read_pass(index=index):
            for instrument in instruments:
                collector.is_instrument_allowed(instrument)
        self.assertEqual(len(queries), 0, [q["sql"] for q in queries])

    def test_cross_request_from_memory(self):
        a = build_checklist(2, prefix="x", answer=False)
        b = build_checklist(0, prefix="x")  # b answers x-gate = yes
        collector = Cooperative(a)
        collector.others = [b]
        index = AnswerIndex(load_instruments([a, b]), CollectedInput.objects.all())
        self.assertEqual(
            visibility(a, collector, index), {"x-gate": True, "x-0": True, "x-1": False}
        )
        self.assertEqual(visibility(a, collector), visibility(a, collector, index))

    def test_unindexed_requests_fall_back_to_the_database(self):
        a = build_checklist(1, prefix="y")
        index = AnswerIndex([], [])
        self.assertIsNone(index.lookup([a], measure="y-gate"))

    def test_load_instruments_is_a_fixed_number_of_queries(self):
        small, large = build_checklist(2, prefix="s"), build_checklist(8, prefix="l")
        with CaptureQueriesContext(connection) as q_small:
            load_instruments([small])
        with CaptureQueriesContext(connection) as q_large:
            load_instruments([large])
        self.assertEqual(len(q_small), len(q_large))


class AnswerIndexContractTests(TestCase):
    """The index trusts its inputs: build it from what the reading collector would see."""

    def test_filtered_inputs_match_the_database_path(self):
        request = build_checklist(4)
        collector = HideYes(request)
        index = AnswerIndex(load_instruments([request]), condition_inputs(collector))
        expected = {"q-gate": True, "q-0": False, "q-1": False, "q-2": False, "q-3": False}
        self.assertEqual(visibility(request, collector), expected)
        self.assertEqual(visibility(request, collector, index), expected)

    def test_an_input_left_out_of_the_index_is_not_seen(self):
        request = build_checklist(2)
        hidden = AnswerIndex(load_instruments([request]), [])
        self.assertEqual(hidden.lookup([request.pk], measure="q-gate"), ([], ["yes", "no"]))

    def test_unfiltered_inputs_are_trusted_as_given(self):
        request = build_checklist(2)
        collector = HideYes(request)
        index = AnswerIndex(load_instruments([request]), CollectedInput.objects.all())
        self.assertTrue(visibility(request, collector, index)["q-0"])  # caller's mistake shows

    def test_duplicate_measure_picks_what_the_database_picks(self):
        request = factories.CollectionRequestFactory.create()
        # Meta.ordering is (segment_id, order, pk): the segment outranks a lower order.
        lower_order = question(request, "dup", order=1)
        first = question(request, "dup", order=5)
        lower_order.segment = factories.CollectionGroupFactory.create(id="z-segment")
        lower_order.save()
        first.segment = factories.CollectionGroupFactory.create(id="a-segment")
        first.save()
        factories.CollectedInputFactory.create(
            instrument=first, collection_request=request, data="yes"
        )
        gate(question(request, "child", order=9), "dup")
        collector = collectors.Collector(request)
        index = AnswerIndex(load_instruments([request]), CollectedInput.objects.all())
        self.assertTrue(visibility(request, collector)["child"])
        self.assertEqual(visibility(request, collector), visibility(request, collector, index))

    def test_pk_conditions_resolve_from_memory_in_their_own_request(self):
        request = build_checklist(2)
        parent = load_instruments([request])[0]
        for instrument in load_instruments([request])[1:]:
            instrument.conditions.update(data_getter=f"instrument:{parent.pk}")
        collector = collectors.Collector(request)
        instruments = load_instruments([request])
        index = AnswerIndex(instruments, list(CollectedInput.objects.all()))
        with CaptureQueriesContext(connection) as queries, read_pass(index=index):
            seen = {i.measure_id: collector.is_instrument_allowed(i) for i in instruments}
        self.assertEqual(seen, {"q-gate": True, "q-0": True, "q-1": False})
        self.assertEqual(len(queries), 0, [q["sql"] for q in queries])
