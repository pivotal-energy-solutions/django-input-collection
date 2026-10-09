"""Evidence questions: the file is the answer; constraints travel with the instrument."""

__author__ = "Steven K"
__date__ = "10/09/26 06:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven K"]

import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase

from ..collection import collectors
from ..collection.merge import merge_requests
from ..collection.methods import EVIDENCE_INPUT, EvidenceMethod
from ..models.utils import clone_collection_request
from ..schema.builder import CollectionRequestBuilder
from ..schema.exporter import CollectionRequestExporter
from ..schema.merged import merged_checklist_payload
from ..schema.mixins import ChecklistConsumerMixin
from ..schema.serializers import CollectionSchemaSerializer
from . import factories
from .test_merge import coop


def schema(**question_extra):
    question = {"measure_id": "site-photo", "text": "Site photo", "type": "open"}
    question.update(question_extra)
    return {"version": "1.0", "name": "Ev", "sections": [{"name": "S", "questions": [question]}]}


class InstrumentConstraintsTests(TestCase):
    def test_builder_stores_and_exporter_round_trips_constraints(self):
        request = CollectionRequestBuilder().build(
            schema(type="integer", constraints={"min": 0, "max": 9})
        )
        instrument = request.collectioninstrument_set.get()
        self.assertEqual(instrument.constraints, {"min": 0, "max": 9})
        exported = CollectionRequestExporter().export(request)
        self.assertEqual(
            exported["sections"][0]["questions"][0]["constraints"], {"min": 0, "max": 9}
        )

    def test_none_values_are_dropped_and_dates_stored_as_text(self):
        request = CollectionRequestBuilder().build(
            schema(
                type="date", constraints={"min_date": datetime.date(2026, 1, 2), "max_date": None}
            )
        )
        self.assertEqual(
            request.collectioninstrument_set.get().constraints, {"min_date": "2026-01-02"}
        )

    def test_exporter_omits_empty_constraints(self):
        exported = CollectionRequestExporter().export(CollectionRequestBuilder().build(schema()))
        self.assertNotIn("constraints", exported["sections"][0]["questions"][0])

    def test_clone_copies_constraints(self):
        instrument = factories.CollectionInstrumentFactory.create(constraints={"accept": ["photo"]})
        cloned = clone_collection_request(instrument.collection_request)
        copy = cloned.collectioninstrument_set.get(measure_id=instrument.measure_id)
        self.assertEqual(copy.constraints, {"accept": ["photo"]})


class EvidenceSchemaTests(TestCase):
    def valid(self, **question_extra):
        serializer = CollectionSchemaSerializer(data=schema(**question_extra))
        return serializer.is_valid(), serializer.errors

    def test_evidence_with_accept_is_valid(self):
        ok, errors = self.valid(type="evidence", constraints={"accept": ["photo"]})
        self.assertTrue(ok, errors)

    def test_evidence_without_constraints_is_valid(self):
        ok, errors = self.valid(type="evidence")
        self.assertTrue(ok, errors)

    def test_evidence_refuses_responses(self):
        ok, _ = self.valid(type="evidence", responses=["Upload Photo"])
        self.assertFalse(ok)

    def test_evidence_refuses_other_constraints(self):
        ok, _ = self.valid(type="evidence", constraints={"min": 1})
        self.assertFalse(ok)

    def test_accept_refuses_unknown_kinds_and_empty_lists(self):
        self.assertFalse(self.valid(type="evidence", constraints={"accept": ["audio"]})[0])
        self.assertFalse(self.valid(type="evidence", constraints={"accept": []})[0])

    def test_accept_is_refused_on_other_types(self):
        self.assertFalse(self.valid(type="open", constraints={"accept": ["photo"]})[0])

    def test_builder_and_exporter_keep_the_type(self):
        request = CollectionRequestBuilder().build(
            schema(type="evidence", constraints={"accept": ["photo"]})
        )
        instrument = request.collectioninstrument_set.get()
        self.assertEqual(instrument.type_id, "evidence")
        self.assertEqual(instrument.bound_suggested_responses.count(), 0)
        question = CollectionRequestExporter().export(request)["sections"][0]["questions"][0]
        self.assertEqual(question["type"], "evidence")
        self.assertEqual(question["constraints"], {"accept": ["photo"]})


class EvidenceMethodTests(TestCase):
    def test_only_the_marker_is_an_answer(self):
        method = EvidenceMethod()
        self.assertEqual(method.clean_input(EVIDENCE_INPUT), "Uploaded")
        with self.assertRaises(ValidationError) as ctx:
            method.clean_input("Upload Photo")
        self.assertEqual(
            ctx.exception.messages, ["An evidence question is answered by uploading a file."]
        )


class EvidencePayloadTests(TestCase):
    def payload(self, request, **kwargs):
        collectors_ = coop(request)
        merged = merge_requests([request], collectors=collectors_)
        data = merged_checklist_payload(merged, collectors=collectors_, **kwargs)
        return data["sections"][0]["questions"][0]

    def test_an_evidence_question_says_so_with_its_accept(self):
        request = CollectionRequestBuilder().build(
            schema(type="evidence", constraints={"accept": ["photo"]})
        )
        question = self.payload(request)
        self.assertTrue(question["evidence_only"])
        self.assertEqual(question["constraints"], {"accept": ["photo"]})

    def test_other_questions_are_not_evidence_only(self):
        question = self.payload(CollectionRequestBuilder().build(schema()))
        self.assertFalse(question["evidence_only"])

    def test_a_consumer_decides(self):
        class Everything(ChecklistConsumerMixin):
            def _is_evidence_only(self, instrument):
                return True

        request = CollectionRequestBuilder().build(schema())
        self.assertTrue(self.payload(request, consumer=Everything())["evidence_only"])

    def test_the_single_request_payload_carries_it_too(self):
        request = CollectionRequestBuilder().build(schema(type="evidence"))
        data = ChecklistConsumerMixin()._build_checklist_response(
            request, collectors.Collector(request), None, "rater"
        )
        self.assertTrue(data["sections"][0]["questions"][0]["evidence_only"])

    def test_clean_raises_validation_error_directly(self):
        self.assertEqual(EvidenceMethod().clean(EVIDENCE_INPUT), "Uploaded")
        with self.assertRaises(ValidationError):
            EvidenceMethod().clean("x")
