"""11.0.0 follow-ups: an AnswerIndex answers only its own collector; payloads honour a consumer."""

__author__ = "Steven Klass"
__date__ = "10/07/26 06:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection import collectors, resolvers
from ..collection.answer_index import AnswerIndex
from ..collection.merge import load_instruments, merge_requests
from ..collection.resolvers import read_pass
from ..models import CollectedInput
from ..schema import ChecklistConsumerMixin, consumer_payload, merged_checklist_payload
from .checklists import build_checklist
from .test_answer_index import HideYes, visibility
from .test_merge import coop


class BoundIndexTests(TestCase):
    """An index bound to one collector's filters is not read by a collector that filters otherwise."""

    def test_a_differently_filtered_collector_reads_the_database(self):
        request = build_checklist(2)
        builder = collectors.Collector(request)
        index = AnswerIndex(
            load_instruments([request]), CollectedInput.objects.all(), collector=builder
        )
        hidden = {"q-gate": True, "q-0": False, "q-1": False}
        self.assertEqual(visibility(request, HideYes(request), index), hidden)
        self.assertTrue(visibility(request, builder, index)["q-0"])

    def test_the_builder_and_alike_collectors_read_from_memory(self):
        request = build_checklist(2)
        instruments = load_instruments([request])
        index = AnswerIndex(
            instruments, list(CollectedInput.objects.all()), collector=collectors.Collector(request)
        )
        alike = collectors.Collector(request)  # same filter key, another instance
        self.assertTrue(index.serves(alike))
        with CaptureQueriesContext(connection) as queries, read_pass(index=index):
            for instrument in instruments:
                alike.is_instrument_allowed(instrument)
        self.assertEqual(len(queries), 0, [q["sql"] for q in queries])

    def test_no_collector_reads_the_database(self):
        request = build_checklist(1)
        child = load_instruments([request])[1]
        bound = AnswerIndex(
            load_instruments([request]), [], complete=True, collector=collectors.Collector(request)
        )
        with read_pass(index=bound):
            _, data, _ = resolvers.resolve(child, "instrument:q-gate")
        self.assertEqual(data["data"], ["yes"])
        unbound = AnswerIndex(load_instruments([request]), [], complete=True)
        with read_pass(index=unbound):
            _, data, _ = resolvers.resolve(child, "instrument:q-gate")
        self.assertEqual(data["data"], [])  # unbound answers for anyone, as before

    def test_merge_binds_its_index_to_its_collector(self):
        request = build_checklist(2)
        collector = collectors.Collector(request)
        merged = merge_requests([request], collectors={request.pk: collector})
        self.assertTrue(merged.index.serves(collector))
        self.assertFalse(merged.index.serves(HideYes(request)))
        other = HideYes(request)
        self.assertEqual(visibility(request, other, merged.index), visibility(request, other))
        # condition_inputs= is vouched for by the caller: deliberately unbound.
        vouched = merge_requests(
            [request],
            collectors={request.pk: collector},
            condition_inputs=CollectedInput.objects.all(),
        )
        self.assertTrue(vouched.index.serves(None))

    def test_the_mixin_binds_its_index_to_its_collector(self):
        request = build_checklist(1)
        collector = collectors.Collector(request)
        *_, index = ChecklistConsumerMixin()._load_checklist(request, collector)
        self.assertTrue(index.serves(collector))
        self.assertFalse(index.serves(HideYes(request)))
        self.assertFalse(index.serves(None))


class Upper(ChecklistConsumerMixin):
    def _section_data(self, group, questions):
        return dict(super()._section_data(group, questions), name="OVERRIDDEN")


class ConsumerPayloadTests(TestCase):
    """Outside a view, the payload still honours a consumer subclass's overrides."""

    def setUp(self):
        self.request = build_checklist(1, prefix="c")
        self.collectors = coop(self.request)
        self.merged = merge_requests([self.request], collectors=self.collectors)

    def names(self, data):
        return [section["name"] for section in data["sections"]]

    def test_a_consumer_class_or_instance_applies_its_overrides(self):
        for consumer in (Upper, Upper()):
            data = merged_checklist_payload(
                self.merged, collectors=self.collectors, consumer=consumer
            )
            self.assertEqual(self.names(data), ["OVERRIDDEN"])

    def test_default_is_the_plain_mixin(self):
        data = merged_checklist_payload(self.merged, collectors=self.collectors)
        self.assertEqual(self.names(data), ["Section A"])

    def test_consumer_payload_is_public(self):
        data = consumer_payload(Upper(), self.merged, collectors=self.collectors)
        self.assertEqual(self.names(data), ["OVERRIDDEN"])
