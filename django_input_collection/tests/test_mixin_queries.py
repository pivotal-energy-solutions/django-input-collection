"""ChecklistConsumerMixin's checklist read must not query per instrument."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.apps import apps
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection import collectors
from ..models import CollectionInstrument
from ..models.utils import get_boundsuggestedresponse_model
from ..schema.mixins import ChecklistConsumerMixin
from . import factories
from .checklists import build_checklist, gate, question


class Consumer(ChecklistConsumerMixin):
    pass


class HideYes(collectors.Collector):
    __noregister__ = True

    def filter_condition_inputs(self, queryset):
        return queryset.exclude(data="yes")


def read(collection_request):
    collector = collectors.Collector(collection_request)
    with CaptureQueriesContext(connection) as queries:
        payload = Consumer()._build_checklist_response(collection_request, collector, None, "rater")
    return payload, len(queries)


class MixinQueryTests(TestCase):
    def test_query_count_does_not_grow_with_instruments(self):
        small, small_count = read(build_checklist(3, prefix="s"))
        large, large_count = read(build_checklist(9, prefix="l"))
        self.assertEqual(small["progress"]["total"], 4)
        self.assertEqual(large["progress"]["total"], 10)
        self.assertEqual(small_count, large_count)
        self.assertEqual(small_count, 8)  # 10.0.0: grew by ~6 per question

    def test_query_count_is_pinned(self):
        # instruments, bound responses (2), condition tree (4), answers (reused by conditions)
        request = build_checklist(27, prefix="x")
        collector = collectors.Collector(request)
        with self.assertNumQueries(8):
            Consumer()._build_checklist_response(request, collector, None, "rater")

    def test_visibility_is_unchanged(self):
        payload, _ = read(build_checklist(4))
        shown = {
            q["measure_id"]: q["is_visible"] for s in payload["sections"] for q in s["questions"]
        }
        self.assertEqual(
            shown, {"q-gate": True, "q-0": True, "q-1": False, "q-2": True, "q-3": False}
        )

    def test_a_filtering_collector_costs_one_more_query(self):
        request = build_checklist(27, prefix="f")
        with self.assertNumQueries(9):  # its condition inputs differ from the answers
            Consumer()._build_checklist_response(request, HideYes(request), None, "rater")

    def test_display_ties_are_by_pk_not_segment(self):
        request = factories.CollectionRequestFactory.create()
        low, high = question(request, "tie-a", order=2), question(request, "tie-b", order=2)
        low.segment = factories.CollectionGroupFactory.create(id="z-segment")
        low.save()
        high.segment = factories.CollectionGroupFactory.create(id="a-segment")
        high.save()
        payload = Consumer()._build_checklist_response(
            request, collectors.Collector(request), None, "rater"
        )
        self.assertEqual([q["id"] for q in payload["sections"][0]["questions"]], [low.pk, high.pk])

    def test_flags_come_from_the_bound_response(self):
        class Flagged(ChecklistConsumerMixin):
            def _get_bound_response_flags(self, bound):
                return {"data": bound.suggested_response.data}

        request = build_checklist(1)
        payload = Flagged()._build_checklist_response(
            request, collectors.Collector(request), None, "r"
        )
        gate_q = payload["sections"][0]["questions"][0]
        self.assertEqual(
            [r["flags"] for r in gate_q["responses"]], [{"data": "yes"}, {"data": "no"}]
        )


def shown(request, collector):
    payload = Consumer()._build_checklist_response(request, collector, None, "rater")
    return {q["id"]: q["is_visible"] for s in payload["sections"] for q in s["questions"]}


def database_path(request, collector):
    """10.0.0: every condition reads its gate from the database (no read pass, no index)."""
    instruments = CollectionInstrument.objects.filter(collection_request=request)
    return {i.id: collector.is_instrument_allowed(i) for i in instruments}


def duplicate_gate(request):
    """Two "dup" instruments; Meta.ordering's first (by segment) is answered, the other isn't."""
    lower_order = question(request, "dup", order=1)
    first = question(request, "dup", order=5)
    lower_order.segment = factories.CollectionGroupFactory.create(id="z-segment")
    lower_order.save()
    first.segment = factories.CollectionGroupFactory.create(id="a-segment")
    first.save()
    factories.CollectedInputFactory.create(instrument=first, collection_request=request, data="yes")
    child = question(request, "dup-child", order=9)
    gate(child, "dup")
    return child


class MixinEquivalenceTests(TestCase):
    """The index path's visibility equals the database path's, question by question."""

    def assertMatchesDatabase(self, request, collector):
        expected = database_path(request, collector)
        self.assertEqual(shown(request, collector), expected)
        return expected

    def test_plain_and_role_filtered_collectors(self):
        for collector_class, visible in ((collectors.Collector, 3), (HideYes, 1)):
            request = build_checklist(4, prefix=collector_class.__name__)
            seen = self.assertMatchesDatabase(request, collector_class(request))
            self.assertEqual(sum(seen.values()), visible)

    def test_duplicate_measure(self):
        request = build_checklist(2)
        child = duplicate_gate(request)
        self.assertTrue(
            self.assertMatchesDatabase(request, collectors.Collector(request))[child.id]
        )

    def test_collector_context_filters_the_index(self):
        mine, theirs = (get_user_model().objects.create(username=n) for n in ("mine", "theirs"))
        request = build_checklist(4, answer=False)
        gate_instrument = CollectionInstrument.objects.get(
            collection_request=request, measure_id="q-gate"
        )
        for user, data in ((mine, "no"), (theirs, "yes")):
            factories.CollectedInputFactory.create(
                instrument=gate_instrument, collection_request=request, user=user, data=data
            )
        for user, odd_visible in ((mine, True), (theirs, False)):
            seen = self.assertMatchesDatabase(request, collectors.Collector(request, user=user))
            odd = CollectionInstrument.objects.get(collection_request=request, measure_id="q-1")
            self.assertIs(seen[odd.id], odd_visible)

    def test_missing_gate_matches_the_database_and_costs_nothing(self):
        counts = []
        for size in (3, 9):
            request = build_checklist(size, prefix=f"m{size}")
            for child in CollectionInstrument.objects.filter(collection_request=request):
                child.conditions.update(data_getter="instrument:nowhere")
            collector = collectors.Collector(request)
            self.assertMatchesDatabase(request, collector)
            with CaptureQueriesContext(connection) as queries:
                shown(request, collector)
            counts.append(len(queries))
        self.assertEqual(counts, [8, 8])

    def test_no_instrument_conditions_skip_the_condition_rows(self):
        mine = get_user_model().objects.create(username="mine")
        for size in (3, 9):
            request = build_checklist(size, prefix=f"n{size}")
            for instrument in CollectionInstrument.objects.filter(collection_request=request):
                instrument.conditions.update(data_getter="attr:measure_id")
            collector = collectors.Collector(request, user=mine)  # would need its own query
            with self.assertNumQueries(8):
                shown(request, collector)


class BoundModelLookupTests(TestCase):
    def test_returns_the_bound_suggested_response_model(self):
        expected = apps.get_model(settings.INPUT_BOUNDSUGGESTEDRESPONSE_MODEL)
        self.assertIs(get_boundsuggestedresponse_model(), expected)
