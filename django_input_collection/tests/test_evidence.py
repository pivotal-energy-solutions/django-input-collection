"""Evidence questions: the file is the answer; constraints travel with the instrument."""

__author__ = "Steven K"
__date__ = "10/09/26 06:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven K"]

import datetime

from django.test import TestCase

from ..models.utils import clone_collection_request
from ..schema.builder import CollectionRequestBuilder
from ..schema.exporter import CollectionRequestExporter
from . import factories


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
