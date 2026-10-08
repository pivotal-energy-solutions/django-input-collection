"""The merged checklist response and the mixin's merged GET."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from ..collection import collectors
from ..collection.merge import merge_requests
from ..models import get_input_model
from ..schema.merged import merged_checklist_payload
from ..schema.mixins import ChecklistConsumerMixin
from . import factories
from .checklists import build_checklist, gate, question
from .test_merge import coop

# Every key the single-request checklist gives a question, plus the merge's request tags.
QUESTION_KEYS = {
    "id",
    "measure_id",
    "text",
    "description",
    "help_text",
    "type",
    "order",
    "is_required",
    "is_visible",
    "constraints",
    "responses",
    "conditions",
    "answer",
    "answers",
    "collection_request",
    "collection_requests",
}


def merging(*requests):
    class Consumer(ChecklistConsumerMixin):
        def get_merge_requests(self, obj):
            return list(requests)

        def get_merge_collectors(self, obj, user, user_role):
            return coop(*requests)

    return Consumer()


class MergedPayloadTests(TestCase):
    def payload(self, *requests, **kwargs):
        collectors_ = coop(*requests)
        merged = merge_requests(requests, collectors=collectors_)
        return merged_checklist_payload(merged, collectors=collectors_, **kwargs)

    def test_shape(self):
        a, b = build_checklist(2, prefix="m"), build_checklist(1, prefix="m", answer=False)
        data = self.payload(a, b)
        self.assertEqual(data["requests"], [a.pk, b.pk])
        (section,) = data["sections"]
        self.assertEqual(
            {k: v for k, v in section.items() if k != "questions"},
            {"name": "Section A", "slug": "section-a", "description": "", "order": 0},
        )
        gate_q = section["questions"][0]
        self.assertEqual(set(gate_q), QUESTION_KEYS)
        self.assertEqual(gate_q["measure_id"], "m-gate")
        self.assertEqual(gate_q["id"], a.collectioninstrument_set.get(measure_id="m-gate").pk)
        self.assertEqual(gate_q["collection_request"], a.pk)
        self.assertEqual(gate_q["collection_requests"], [a.pk, b.pk])
        self.assertEqual(gate_q["answer"]["data"], "yes")
        self.assertEqual([r["value"] for r in gate_q["responses"]], ["yes", "no"])
        self.assertEqual(data["progress"]["total"], 3)
        child = section["questions"][1]
        self.assertEqual(
            child["conditions"],
            [{"type": "instrument", "source": "m-gate", "match_type": "match", "values": []}],
        )
        self.assertTrue(child["is_visible"])
        self.assertFalse(section["questions"][2]["is_visible"])

    def test_question_extras(self):
        a = build_checklist(1, prefix="e")
        data = self.payload(a, question_extras=lambda q, p: {"tag": q.measure_id.upper()})
        self.assertEqual(data["sections"][0]["questions"][0]["tag"], "E-GATE")

    def test_answer_payload_and_visibility_overrides(self):
        a = build_checklist(1, prefix="o")
        data = self.payload(
            a, visibility={"o-gate": False}, answer_payload=lambda row: {"value": row.data}
        )
        gate_q = data["sections"][0]["questions"][0]
        self.assertEqual(gate_q["answer"], {"value": "yes"})
        self.assertEqual(gate_q["answers"], [{"value": "yes"}])
        self.assertFalse(gate_q["is_visible"])
        self.assertEqual(data["progress"]["visible"], 0)

    def test_multi_value_answers_are_what_conditions_read(self):
        request = factories.CollectionRequestFactory.create()
        parent = question(request, "mv-parent", responses=("old", "new"))
        child = question(request, "mv-child", order=1)
        gate(child, "mv-parent", match_type="contains", match_data="old")
        earlier = timezone.now() - datetime.timedelta(hours=1)
        for data, created in (("old", earlier), ("new", timezone.now())):
            row = factories.CollectedInputFactory.create(
                instrument=parent, collection_request=request, data=data
            )
            get_input_model().objects.filter(pk=row.pk).update(date_created=created)
        questions = self.payload(request)["sections"][0]["questions"]
        parent_q, child_q = questions
        self.assertEqual(parent_q["answer"]["data"], "new")  # the newest row, as before
        self.assertEqual([a["data"] for a in parent_q["answers"]], ["old", "new"])
        self.assertTrue(child_q["is_visible"])  # "contains old" sees the displayed set

    def test_answers_come_from_the_answering_request_only(self):
        a, b = build_checklist(0, prefix="w"), build_checklist(0, prefix="w")
        data = self.payload(a, b)
        gate_q = data["sections"][0]["questions"][0]
        self.assertEqual(len(gate_q["answers"]), 1)
        self.assertEqual(gate_q["answers"][0]["id"], gate_q["answer"]["id"])

    def test_is_required_if_any_request_requires_it(self):
        a, b = build_checklist(0, prefix="r"), build_checklist(0, prefix="r", answer=False)
        required = factories.ResponsePolicyFactory.create(nickname="required", required=True)
        b.collectioninstrument_set.update(response_policy=required)  # optional on owner A
        data = self.payload(a, b)
        gate_q = data["sections"][0]["questions"][0]
        self.assertEqual(gate_q["collection_request"], a.pk)
        self.assertIs(gate_q["is_required"], True)
        self.assertEqual(data["progress"]["required_total"], 1)
        self.assertEqual(data["progress"]["required_answered"], 1)

    def test_optional_everywhere_is_not_required(self):
        a, b = build_checklist(0, prefix="n"), build_checklist(0, prefix="n", answer=False)
        data = self.payload(a, b)
        self.assertIs(data["sections"][0]["questions"][0]["is_required"], False)
        self.assertEqual(data["progress"]["required_total"], 0)

    def test_unanswered_question(self):
        a = build_checklist(0, prefix="u", answer=False)
        gate_q = self.payload(a)["sections"][0]["questions"][0]
        self.assertIsNone(gate_q["answer"])
        self.assertEqual(gate_q["answers"], [])

    def test_payload_queries_do_not_grow(self):
        counts = []
        for size in (3, 9):
            a, b = (
                build_checklist(size, prefix=f"p{size}"),
                build_checklist(size, prefix=f"q{size}"),
            )
            with CaptureQueriesContext(connection) as queries:
                self.payload(a, b)
            counts.append(len(queries))
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(counts[0], 8)  # the merge's 8; the payload itself reads nothing


class MixinMergedGetTests(TestCase):
    def test_merge_requests_hook_switches_the_checklist_shape(self):
        a, b = build_checklist(1, prefix="h"), build_checklist(1, prefix="h", answer=False)
        data = merging(a, b)._build_merged_response(object(), None, "rater")
        self.assertEqual(data["requests"], [a.pk, b.pk])

    def test_no_merge_requests_keeps_the_single_request_checklist(self):
        self.assertIsNone(ChecklistConsumerMixin().get_merge_requests(object()))

    def test_checklist_action_uses_the_merged_response(self):
        a, b = build_checklist(1, prefix="c"), build_checklist(1, prefix="c", answer=False)
        consumer = merging(a, b)
        consumer.get_object = object
        consumer.get_user_role = lambda request: "rater"
        consumer.get_collection_request = lambda obj: self.fail("single-request path taken")

        class Request:
            user = None

        response = consumer.checklist(Request())
        self.assertEqual(response.data["requests"], [a.pk, b.pk])

    def test_collector_errors_are_permission_denied(self):
        a = build_checklist(1, prefix="d")
        consumer = merging(a)

        def refuse(obj, user, user_role):
            raise ValueError("not yours")

        consumer.get_merge_collectors = refuse
        with self.assertRaises(PermissionDenied):
            consumer._build_merged_response(object(), None, "rater")

    def test_the_mixin_answer_serializer_is_used(self):
        a = build_checklist(0, prefix="s")
        consumer = merging(a)
        consumer._serialize_answer = lambda row: {"custom": row.data}
        data = consumer._build_merged_response(object(), None, "rater")
        self.assertEqual(data["sections"][0]["questions"][0]["answer"], {"custom": "yes"})

    def read(self, size, count):
        requests = [build_checklist(size, prefix=f"r{size}-{count}-{n}") for n in range(count)]
        with CaptureQueriesContext(connection) as queries:
            merging(*requests)._build_merged_response(object(), None, "rater")
        return len(queries)

    def test_merged_get_queries_do_not_grow_with_questions_or_requests(self):
        self.assertEqual(self.read(3, 2), self.read(9, 2))
        self.assertEqual(self.read(3, 2), self.read(3, 3))
        self.assertEqual(self.read(3, 2), 8)


def strip_merge_keys(payload):
    """A merged payload less its documented additions, to compare with the single-request one."""
    sections = [
        dict(
            section,
            questions=[
                {k: v for k, v in q.items() if k not in MERGE_ONLY_KEYS}
                for q in section["questions"]
            ],
        )
        for section in payload["sections"]
    ]
    return {"sections": sections, "progress": payload["progress"]}


MERGE_ONLY_KEYS = {"collection_request", "collection_requests", "answers"}


class MergedParityTests(TestCase):
    """A merge of one request is the single-request checklist plus the documented keys."""

    def build(self):
        request = build_checklist(3, prefix="par")
        factories.CollectionInstrumentFactory.create(
            collection_request=request,
            measure=factories.MeasureFactory.create(id="par-general"),
            group=None,
            order=4,
        )
        question(request, "par-other", group="Section B", order=2, responses=("x",))
        return request

    def both(self, consumer, request):
        collector = collectors.Collector(request)
        single = consumer._build_checklist_response(request, collector, None, "rater")
        merged = merge_requests([request], collectors={request.pk: collector})
        from ..schema.merged import consumer_payload

        return single, consumer_payload(consumer, merged, collectors={request.pk: collector})

    def assertParity(self, consumer):
        request = self.build()
        single, merged = self.both(consumer, request)
        self.assertEqual(merged["requests"], [request.pk])
        self.assertEqual(
            [s["name"] for s in single["sections"]], ["General", "Section A", "Section B"]
        )
        self.assertEqual(
            {"sections": single["sections"], "progress": single["progress"]},
            strip_merge_keys(merged),
        )
        return merged

    def test_default_consumer(self):
        self.assertParity(ChecklistConsumerMixin())
        request = self.build()
        collector = collectors.Collector(request)
        merged = merge_requests([request], collectors={request.pk: collector})
        payload = merged_checklist_payload(merged, collectors={request.pk: collector})
        _, via_consumer = self.both(ChecklistConsumerMixin(), request)
        self.assertEqual(payload, via_consumer)

    def test_per_question_overrides_are_honoured(self):
        class Overriding(ChecklistConsumerMixin):
            def _get_bound_response_flags(self, bound):
                return {"is_failure": bound.suggested_response.data == "no"}

            def _serialize_condition(self, condition, instrument_by_measure):
                return {"getter": condition.data_getter}

            def _get_instrument_constraints(self, collector, instrument):
                return {"max": instrument.order}

            def _slugify(self, text):
                return f"slug-{text}"

        merged = self.assertParity(Overriding())
        sections = {s["name"]: s for s in merged["sections"]}
        self.assertEqual(sections["Section A"]["slug"], "slug-Section A")
        gate_q, child = sections["Section A"]["questions"][:2]
        self.assertEqual(gate_q["responses"][1], {"value": "no", "flags": {"is_failure": True}})
        self.assertEqual(child["conditions"], [{"getter": "instrument:par-gate"}])
        self.assertEqual(child["constraints"], {"max": 1})

    def test_the_10_0_0_flags_hook_still_applies(self):
        class Legacy(ChecklistConsumerMixin):
            def _get_response_flags(self, instrument, suggested_response):
                return {"legacy": suggested_response.data}

        merged = self.assertParity(Legacy())
        gate_q = merged["sections"][1]["questions"][0]
        self.assertEqual(gate_q["responses"][0]["flags"], {"legacy": "yes"})

    def test_overrides_cost_no_queries(self):
        class Flagged(ChecklistConsumerMixin):
            def _get_bound_response_flags(self, bound):
                return {"value": bound.suggested_response.data}

        counts = []
        for size in (3, 9):
            request = build_checklist(size, prefix=f"oq{size}")
            consumer = Flagged()

            class Merging(type(consumer)):
                def get_merge_requests(self, obj):
                    return [request]

                def get_merge_collectors(self, obj, user, user_role):
                    return {request.pk: collectors.Collector(request)}

            with CaptureQueriesContext(connection) as queries:
                Merging()._build_merged_response(object(), None, "rater")
            counts.append(len(queries))
        self.assertEqual(counts, [8, 8])
