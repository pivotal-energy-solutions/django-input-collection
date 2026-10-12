"""Gate reads: a copy reads its own rows for gates in its group, everything else unrepeated rows."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from unittest import mock

from django.test import TestCase

from ..collection import collectors
from ..collection.answer_index import AnswerIndex
from ..collection.merge import load_instruments
from ..collection.repeat import CurrentCopy, copy_scope
from ..collection.resolvers import read_pass
from ..managers import CollectedInputQuerySet, UserLatestCollectedInputQuerySet
from ..models import get_input_model
from ..schema.mixins import ChecklistConsumerMixin
from . import factories
from .checklists import build_checklist, gate, question
from .repeats import answer, doors


def index_for(request):
    rows = list(get_input_model().objects.order_by("date_created", "id"))
    return AnswerIndex(load_instruments([request]), rows, complete=True)


def user_latest_filter_for_context(self, **context):
    """UserLatestCollectedInputQuerySet.filter_for_context, run on the queryset as filtered so far.

    The test model's manager is a plain CollectedInputQuerySet; this swaps the clone's class so
    the real "latest row per instrument" subquery runs on whatever was filtered before it.
    """
    if isinstance(self, UserLatestCollectedInputQuerySet):
        return self.filter(**context)  # its super() call: the base hook, unpatched
    queryset = self._chain()
    queryset.__class__ = UserLatestCollectedInputQuerySet
    return queryset.filter_for_context(**context)


class OutsideGateTests(TestCase):
    """A gate outside any copy reads only unrepeated rows."""

    def setUp(self):
        self.request = factories.CollectionRequestFactory.create()
        self.parent = question(self.request, "parent", responses=("yes", "no"))
        self.child = question(self.request, "child", order=1)
        gate(self.child, "parent")

    def allowed(self, collector=None, index=None):
        collector = collector or collectors.Collector(self.request)
        with read_pass(index=index):
            return collector.is_instrument_allowed(self.child)

    def test_a_repeated_row_does_not_open_an_outside_gate(self):
        answer(self.parent, "yes", repeat_index=2)
        self.assertFalse(self.allowed())
        self.assertFalse(self.allowed(index=index_for(self.request)))

    def test_the_unrepeated_row_still_does(self):
        answer(self.parent, "yes", repeat_index=2)
        answer(self.parent, "yes")
        self.assertTrue(self.allowed())
        self.assertTrue(self.allowed(index=index_for(self.request)))

    def test_a_write_copy_in_the_collector_context_does_not_narrow_gate_reads(self):
        answer(self.parent, "yes")
        self.assertTrue(self.allowed(collectors.Collector(self.request, repeat_index=2)))

    def test_a_copy_scope_does_not_reach_a_gate_outside_its_group(self):
        answer(self.parent, "yes")
        with copy_scope(CurrentCopy(group_id=999, group_slug="windows", index=1)):
            self.assertTrue(self.allowed())
            self.assertTrue(self.allowed(index=index_for(self.request)))


class SiblingScopeTests(TestCase):
    """Inside a copy, a gate in the same group reads that copy's row only."""

    def setUp(self):
        self.request, self.group, self.found = doors()
        self.area = self.found["door-glazing-area"]
        answer(self.found["door-glazed"], "no", repeat_index=1)
        answer(self.found["door-glazed"], "yes", repeat_index=2)

    def copy(self, n):
        return CurrentCopy(self.group.pk, self.group.slug, n)

    def allowed(self, copy_index, index=None):
        collector = collectors.Collector(self.request)
        copy = None if copy_index is None else self.copy(copy_index)
        with read_pass(index=index), copy_scope(copy):
            return collector.is_instrument_allowed(self.area)

    def test_database_path(self):
        self.assertEqual([self.allowed(n) for n in (1, 2, 3, None)], [False, True, False, False])

    def test_index_path(self):
        index = index_for(self.request)
        self.assertEqual(
            [self.allowed(n, index) for n in (1, 2, 3, None)], [False, True, False, False]
        )

    def test_copies_do_not_share_a_read_pass_entry(self):
        collector = collectors.Collector(self.request)
        seen = []
        with read_pass():
            for n in (2, 1, 2):
                with copy_scope(self.copy(n)):
                    seen.append(collector.is_instrument_allowed(self.area))
        self.assertEqual(seen, [True, False, True])

    def test_index_lookup_scopes_by_copy(self):
        index = index_for(self.request)
        requests = [self.request.pk]
        two = index.lookup(requests, measure="door-glazed", copy=self.copy(2))
        one = index.lookup(requests, measure="door-glazed", copy=self.copy(1))
        self.assertEqual(two[0], ["yes"])
        self.assertEqual(one[0], ["no"])
        self.assertEqual(index.lookup(requests, measure="door-glazed")[0], [])


class SlugScopeTests(TestCase):
    """Groups match by slug: a copy of another request's same-slug group scopes this one's gate."""

    def setUp(self):
        self.request, self.group, self.found = doors()
        self.other_request, self.other_group, _ = doors()
        self.assertNotEqual(self.group.pk, self.other_group.pk)
        self.assertEqual(self.group.slug, self.other_group.slug)
        answer(self.found["door-glazed"], "no", repeat_index=1)
        answer(self.found["door-glazed"], "yes", repeat_index=2)

    def allowed(self, n, index=None):
        collector = collectors.Collector(self.request)
        copy = CurrentCopy(self.other_group.pk, self.other_group.slug, n)
        with read_pass(index=index), copy_scope(copy):
            return collector.is_instrument_allowed(self.found["door-glazing-area"])

    def test_database_path(self):
        self.assertEqual([self.allowed(n) for n in (1, 2)], [False, True])

    def test_index_path(self):
        index = index_for(self.request)
        self.assertEqual([self.allowed(n, index) for n in (1, 2)], [False, True])

    def test_index_lookup(self):
        index = index_for(self.request)
        copy = CurrentCopy(self.other_group.pk, self.other_group.slug, 2)
        found = index.lookup([self.request.pk], measure="door-glazed", copy=copy)
        self.assertEqual(found[0], ["yes"])


class LatestPerInstrumentQuerySetTests(TestCase):
    """A latest-row-per-instrument filter_for_context must not collapse copies into one row."""

    def setUp(self):
        self.request, self.group, self.found = doors()
        answer(self.found["door-glazed"], "yes", repeat_index=1)
        answer(self.found["door-glazed"], "no", repeat_index=2)  # newest row of the instrument

    def allowed(self, n):
        collector = collectors.Collector(self.request)
        copy = None if n is None else CurrentCopy(self.group.pk, self.group.slug, n)
        with read_pass(), copy_scope(copy):
            return collector.is_instrument_allowed(self.found["door-glazing-area"])

    def test_each_copy_reads_its_own_latest_row(self):
        with mock.patch.object(
            CollectedInputQuerySet, "filter_for_context", user_latest_filter_for_context
        ):
            self.assertEqual([self.allowed(n) for n in (1, 2, None)], [True, False, False])


class SingleRequestChecklistTests(TestCase):
    def test_a_repeated_row_is_not_the_shown_answer(self):
        request = build_checklist(1)
        answer(request.collectioninstrument_set.get(measure_id="q-0"), "a", repeat_index=1)
        payload = ChecklistConsumerMixin()._build_checklist_response(
            request, collectors.Collector(request), None, "rater"
        )
        shown = {q["measure_id"]: q["answer"] for s in payload["sections"] for q in s["questions"]}
        self.assertIsNone(shown["q-0"])
        self.assertEqual(payload["progress"]["answered"], 1)  # the gate's answer only

    def test_a_write_copy_in_the_collector_context_does_not_narrow_gate_reads(self):
        request = build_checklist(2)  # q-gate answered "yes" (unrepeated); q-0 needs "yes"
        payload = ChecklistConsumerMixin()._build_checklist_response(
            request, collectors.Collector(request, repeat_index=2), None, "rater"
        )
        shown = {
            q["measure_id"]: q["is_visible"] for s in payload["sections"] for q in s["questions"]
        }
        self.assertEqual(shown, {"q-gate": True, "q-0": True, "q-1": False})
