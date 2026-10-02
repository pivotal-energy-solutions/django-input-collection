"""Per-home copies of a checklist keep each question's context."""

__author__ = "Steven K"
__date__ = "10/02/26 12:34 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven K"]

from django.test import TestCase

from ..models.utils import clone_collection_request
from . import factories


class CloneKeepsContextTests(TestCase):
    def test_clone_copies_instrument_context(self):
        instrument = factories.CollectionInstrumentFactory.create(
            context={"provides_for": ["simulation.window"]}
        )
        cloned = clone_collection_request(instrument.collection_request)
        copy = cloned.collectioninstrument_set.get(measure_id=instrument.measure_id)
        self.assertNotEqual(copy.pk, instrument.pk)
        self.assertEqual(copy.context, {"provides_for": ["simulation.window"]})
