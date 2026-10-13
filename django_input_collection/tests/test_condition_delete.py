"""Deleting what a Condition gates deletes the Condition, whatever listens for deletes."""

__author__ = "Steven Klass"
__date__ = "10/13/26 02:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db.models.signals import post_delete
from django.test import TestCase

from ..models import CollectionInstrument, Condition, RepeatGroup
from . import factories
from .checklists import question
from .repeats import repeat_group


def _ignore(sender, instance, **kwargs):
    pass


class ConditionDeleteTests(TestCase):
    """A post_delete receiver for every model (haystack's RealtimeSignalProcessor does this)
    stops Django fast-deleting. A python-level CASCADE from a nullable FK then nulls the FK
    before deleting the rows, which on MariaDB breaks condition_instrument_xor_repeat_group."""

    def setUp(self):
        post_delete.connect(_ignore)
        self.addCleanup(post_delete.disconnect, _ignore)
        self.request = factories.CollectionRequestFactory.create()
        self.door = question(self.request, "door-type")
        self.group = repeat_group(self.request)
        condition_group = factories.ConditionGroupFactory.create()
        Condition.objects.create(
            instrument=self.door, condition_group=condition_group, data_getter="instrument:x"
        )
        Condition.objects.create(
            repeat_group=self.group, condition_group=condition_group, data_getter="instrument:x"
        )

    def test_deleting_an_instrument_deletes_its_conditions(self):
        self.door.delete()
        self.assertEqual(
            list(Condition.objects.values_list("repeat_group", flat=True)), [self.group.pk]
        )

    def test_deleting_instruments_in_bulk_deletes_their_conditions(self):
        CollectionInstrument.objects.filter(collection_request=self.request).delete()
        self.assertFalse(Condition.objects.filter(instrument__isnull=False).exists())

    def test_deleting_a_group_deletes_its_conditions(self):
        RepeatGroup.objects.filter(pk=self.group.pk).delete()
        self.assertEqual(
            list(Condition.objects.values_list("instrument", flat=True)), [self.door.pk]
        )

    def test_deleting_a_request_deletes_every_condition_under_it(self):
        self.request.delete()
        self.assertFalse(Condition.objects.exists())
