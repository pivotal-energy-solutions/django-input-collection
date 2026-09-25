"""test_condition_queries.py: Condition evaluation must not query per instrument"""

__author__ = "Steven Klass"
__date__ = "09/25/26"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..api.restframework.serializers import CollectionInstrumentSerializer
from ..collection import collectors
from . import factories

CONDITION_TABLES = (
    "django_input_collection_condition",
    "django_input_collection_conditiongroup",
    "django_input_collection_case",
)


def build_request(num_children: int):
    """A parent instrument gating ``num_children`` instruments; odd children are blocked."""
    collection_request = factories.CollectionRequestFactory.create()
    parent = factories.CollectionInstrumentFactory.create(collection_request=collection_request)
    factories.CollectedInputFactory.create(
        instrument=parent, collection_request=collection_request, data="foo"
    )
    for i in range(num_children):
        child = factories.CollectionInstrumentFactory.create(collection_request=collection_request)
        case = factories.CaseFactory.create(
            match_type="match" if i % 2 == 0 else "mismatch", match_data="foo"
        )
        nested = factories.ConditionGroupFactory.create(requirement_type="all-pass", cases=[case])
        group = factories.ConditionGroupFactory.create(
            requirement_type="all-pass", child_groups=[nested]
        )
        factories.ConditionFactory.create(
            instrument=child, condition_group=group, data_getter=f"instrument:{parent.id}"
        )
    return collection_request, parent


def condition_queries(queries) -> int:
    return sum(1 for q in queries if any(t in q["sql"] for t in CONDITION_TABLES))


class ConditionQueryCountTests(TestCase):
    def _get_instruments(self, num_children):
        collection_request, parent = build_request(num_children)
        collector = collectors.Collector(collection_request)
        with CaptureQueriesContext(connection) as queries:
            allowed = set(collector.get_instruments(active=True).values_list("id", flat=True))
        return allowed, parent, condition_queries(queries)

    def _list_serializer(self, num_children):
        collection_request, parent = build_request(num_children)
        collector = collectors.Collector(collection_request)
        with CaptureQueriesContext(connection) as queries:
            data = CollectionInstrumentSerializer(
                instance=collection_request.collectioninstrument_set.all(),
                many=True,
                context={"collector": collector},
            ).data
        allowed = {x["id"] for x in data if x["is_condition_met"]}
        return allowed, parent, condition_queries(queries)

    def test_get_instruments_condition_queries_do_not_scale(self):
        allowed_small, parent, small = self._get_instruments(2)
        self.assertEqual(len(allowed_small), 2)  # parent + the one passing child
        self.assertIn(parent.id, allowed_small)

        allowed_large, _parent, large = self._get_instruments(6)
        self.assertEqual(len(allowed_large), 4)  # parent + 3 passing children
        self.assertEqual(small, large)

    def test_list_serializer_condition_queries_do_not_scale(self):
        allowed_small, parent, small = self._list_serializer(2)
        self.assertEqual(len(allowed_small), 2)
        self.assertIn(parent.id, allowed_small)

        allowed_large, _parent, large = self._list_serializer(6)
        self.assertEqual(len(allowed_large), 4)
        self.assertEqual(small, large)

    def test_unprefetched_instrument_still_tests_conditions(self):
        """Callers that don't prefetch keep working (they just pay the queries)."""
        collection_request, _parent = build_request(2)
        children = collection_request.collectioninstrument_set.filter(conditions__isnull=False)
        results = sorted(child.test_conditions() for child in children.order_by("id"))
        self.assertEqual(results, [False, True])
