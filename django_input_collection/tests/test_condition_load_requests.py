"""ChecklistConsumerMixin.get_condition_load_requests: widened gates read from the index."""

__author__ = "Steven Klass"
__date__ = "10/08/26 10:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import connection
from django.db.models import F
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection import collectors
from ..collection.merge import load_condition_instruments
from ..models import CollectionInstrument, CollectionRequest
from ..schema.mixins import ChecklistConsumerMixin
from . import factories
from .checklists import gate, question


class Cooperative(collectors.Collector):
    """Searches ``others`` after its own request, as a consumer seeds it."""

    __noregister__ = True
    others = ()

    def get_condition_requests(self, instrument):
        return [instrument.collection_request, *self.others]


class HideYes(Cooperative):
    __noregister__ = True

    def filter_condition_inputs(self, queryset):
        return queryset.exclude(data="yes")


class Consumer(ChecklistConsumerMixin):
    def __init__(self, others=None):
        self.others = others
        self.loaded = None

    def get_condition_load_requests(self, collection_request, collector):
        return self.others

    def condition_requests_loaded(self, collection_request, collector, requests):
        self.loaded = requests
        collector.others = requests[1:]


def answer(instrument, data):
    factories.CollectedInputFactory.create(
        instrument=instrument, collection_request=instrument.collection_request, data=data
    )


def sibling(data="yes", ask=True):
    """Another request asking (and answering) the gate."""
    request = factories.CollectionRequestFactory.create()
    if ask:
        answer(question(request, "gate"), data)
    return request


def own_checklist(size=4):
    """The gate (asked here, unanswered) and ``size`` children gated on it, even ones on "yes"."""
    request = factories.CollectionRequestFactory.create()
    question(request, "gate")
    for i in range(size):
        child = question(request, f"child-{i}", order=i + 1)
        gate(child, "gate", match_data="yes" if i % 2 == 0 else "no")
    return request


def shown(consumer, request, collector):
    payload = consumer._build_checklist_response(request, collector, None, "rater")
    return {q["id"]: q["is_visible"] for s in payload["sections"] for q in s["questions"]}


def database_path(request, collector):
    instruments = CollectionInstrument.objects.filter(collection_request=request)
    return {i.id: collector.is_instrument_allowed(i) for i in instruments}


class ConditionLoadRequestTests(TestCase):
    def read(self, request, others, collector_class=Cooperative):
        collector = collector_class(request)
        consumer = Consumer(others)
        with CaptureQueriesContext(connection) as queries:
            seen = shown(consumer, request, collector)
        return seen, len(queries), consumer, collector

    def test_query_count_is_flat_across_requests(self):
        counts = []
        for size in (1, 3):
            request = own_checklist()
            seen, count, *_ = self.read(request, [sibling() for _ in range(size)])
            self.assertEqual(sum(seen.values()), 3)  # gate + the two "yes" children
            counts.append(count)
        # instruments, bound responses, condition tree (4), answers, condition rows
        self.assertEqual(counts, [8, 8])

    def test_a_queryset_costs_no_more_than_a_list(self):
        request = own_checklist()
        others = [sibling(), sibling()]
        _seen, as_list, *_ = self.read(request, others)
        queryset = CollectionRequest.objects.filter(pk__in=[r.pk for r in others])
        _seen, as_queryset, *_ = self.read(request, queryset)
        self.assertEqual(as_list, as_queryset)

    def test_without_the_hook_widened_gates_hit_the_database(self):
        request = own_checklist()
        others = [sibling(), sibling(), sibling()]
        _seen, hooked, *_ = self.read(request, others)
        collector = Cooperative(request)
        collector.others = others
        with CaptureQueriesContext(connection) as queries:
            shown(Consumer(), request, collector)
        self.assertGreater(len(queries), hooked)

    def test_visibility_equals_the_database_path(self):
        for collector_class, data in ((Cooperative, "yes"), (Cooperative, "no"), (HideYes, "yes")):
            request = own_checklist()
            others = [sibling(data, ask=False), sibling(data), sibling("yes")]
            seen, _count, _consumer, collector = self.read(request, others, collector_class)
            self.assertEqual(seen, database_path(request, collector))

    def test_own_answer_wins(self):
        request = own_checklist()
        answer(CollectionInstrument.objects.get(collection_request=request, measure="gate"), "no")
        seen, _count, _consumer, collector = self.read(request, [sibling("yes")])
        self.assertEqual(seen, database_path(request, collector))
        self.assertEqual(sum(seen.values()), 3)  # gate + the two "no" children

    def test_display_is_own_request_only(self):
        request = own_checklist(2)
        others = [sibling()]
        collector = Cooperative(request)
        instruments, answers, index = Consumer(others)._load_checklist(request, collector)
        self.assertEqual({i.collection_request_id for i in instruments}, {request.pk})
        self.assertEqual(answers, {})
        self.assertEqual([i.measure_id for i in instruments], ["gate", "child-0", "child-1"])
        self.assertTrue(index.covers([request.pk, others[0].pk]))
        self.assertTrue(index.serves(collector))
        self.assertFalse(index.serves(HideYes(request)))  # bound to its collector's filter

    def test_none_keeps_the_own_request(self):
        request = own_checklist()
        consumer = Consumer(None)
        _instruments, _answers, index = consumer._load_checklist(request, Cooperative(request))
        self.assertIsNone(consumer.loaded)
        self.assertFalse(index.covers([sibling().pk]))


class LoadedRequestTests(TestCase):
    def test_list_order_as_given_less_own_duplicates_and_empty(self):
        request = own_checklist(1)
        first, second, empty = sibling(), sibling(), sibling(ask=False)
        _instruments, requests = load_condition_instruments(
            request, [second, request, first.pk, empty, second]
        )
        self.assertEqual(requests, [request, second, first.pk])

    def test_queryset_order_by_is_honoured(self):
        request = own_checklist(1)
        a, b, c = sibling(), sibling(), sibling()
        CollectionRequest.objects.filter(pk=a.pk).update(max_instrument_inputs=2)
        CollectionRequest.objects.filter(pk__in=[b.pk, c.pk]).update(max_instrument_inputs=1)
        queryset = CollectionRequest.objects.exclude(pk=sibling(ask=False).pk)
        for order, expected in (
            (("max_instrument_inputs",), [b, c, a]),
            (("-max_instrument_inputs",), [a, b, c]),  # pk breaks the tie
        ):
            with self.assertNumQueries(6):  # instruments + prefetches only
                instruments, requests = load_condition_instruments(
                    request, queryset.order_by(*order)
                )
            self.assertEqual(requests, [request, *expected])
            self.assertIs(requests[0], request)
            by_request = {i.collection_request_id: i.collection_request for i in instruments}
            self.assertEqual(list(by_request.values()), [request, a, b, c])
            self.assertTrue(
                all(
                    i.collection_request is by_request[i.collection_request_id] for i in instruments
                )
            )  # one object per request

    def test_an_unfoldable_queryset_is_evaluated(self):
        request = own_checklist(1)
        a, b = sibling(), sibling()
        queryset = CollectionRequest.objects.filter(pk__in=[a.pk, b.pk])
        for unfoldable in (queryset.order_by(F("pk").desc()), queryset.order_by("-pk")[:2]):
            with self.assertNumQueries(7):  # the queryset, then instruments + prefetches
                _instruments, requests = load_condition_instruments(request, unfoldable)
            self.assertEqual(requests, [request, b, a])


class ChecklistInputsTests(TestCase):
    def test_display_filter_leaves_condition_reads_alone(self):
        class HidesYesAnswers(ChecklistConsumerMixin):
            def get_checklist_inputs(self, collection_request, collector):
                return (
                    super().get_checklist_inputs(collection_request, collector).exclude(data="yes")
                )

        request = own_checklist(2)
        gate_instrument = CollectionInstrument.objects.get(
            collection_request=request, measure="gate"
        )
        answer(gate_instrument, "yes")
        collector = collectors.Collector(request)
        _instruments, answers, _index = HidesYesAnswers()._load_checklist(request, collector)
        self.assertEqual(answers, {})
        seen = shown(HidesYesAnswers(), request, collector)
        self.assertEqual(seen, database_path(request, collector))
        self.assertEqual(sum(seen.values()), 2)  # the gate's "yes" still opens child-0
