"""ChecklistConsumerMixin's checklist read must not query per instrument."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection import collectors
from ..models import CollectionInstrument
from ..models.utils import get_boundsuggestedresponse_model
from ..schema.mixins import ChecklistConsumerMixin
from .checklists import build_checklist


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
        self.assertEqual(small_count, 9)  # 10.0.0: grew by ~6 per question

    def test_query_count_is_pinned(self):
        # instruments, bound responses (2), condition tree (4), answers, condition inputs
        request = build_checklist(27, prefix="x")
        collector = collectors.Collector(request)
        with self.assertNumQueries(9):
            Consumer()._build_checklist_response(request, collector, None, "rater")

    def test_visibility_is_unchanged(self):
        payload, _ = read(build_checklist(4))
        shown = {
            q["measure_id"]: q["is_visible"] for s in payload["sections"] for q in s["questions"]
        }
        self.assertEqual(
            shown, {"q-gate": True, "q-0": True, "q-1": False, "q-2": True, "q-3": False}
        )

    def test_index_path_matches_the_database_path(self):
        """Visibility read through the AnswerIndex equals 10.0.0's per-condition database reads."""
        for collector_class in (collectors.Collector, HideYes):
            request = build_checklist(4, prefix=collector_class.__name__)
            collector = collector_class(request)
            payload = Consumer()._build_checklist_response(request, collector, None, "rater")
            shown = {q["id"]: q["is_visible"] for s in payload["sections"] for q in s["questions"]}
            instruments = CollectionInstrument.objects.filter(collection_request=request)
            expected = {i.id: collector.is_instrument_allowed(i) for i in instruments}
            self.assertEqual(shown, expected)
            self.assertEqual(sum(shown.values()), 1 if collector_class is HideYes else 3)

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


class BoundModelLookupTests(TestCase):
    def test_returns_the_bound_suggested_response_model(self):
        expected = apps.get_model(settings.INPUT_BOUNDSUGGESTEDRESPONSE_MODEL)
        self.assertIs(get_boundsuggestedresponse_model(), expected)
