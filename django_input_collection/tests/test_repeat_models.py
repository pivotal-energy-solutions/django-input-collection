"""RepeatGroup, CollectionInstrument.repeat_group, CollectedInput.repeat_index, group conditions."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import IntegrityError, transaction
from django.test import TestCase

from ..models import Condition, get_input_model
from . import factories
from .checklists import question
from .repeats import answer, in_group, repeat_group


class RepeatModelTests(TestCase):
    def setUp(self):
        self.request = factories.CollectionRequestFactory.create()

    def test_a_group_slug_is_unique_per_request(self):
        repeat_group(self.request, slug="doors")
        repeat_group(factories.CollectionRequestFactory.create(), slug="doors")  # another request
        with transaction.atomic(), self.assertRaises(IntegrityError):
            repeat_group(self.request, slug="doors")

    def test_instruments_join_a_group_and_outlive_it(self):
        group = repeat_group(self.request)
        door = in_group(question(self.request, "door-type"), group)
        self.assertEqual(list(group.instruments.all()), [door])
        self.assertEqual(list(self.request.repeat_groups.all()), [group])
        self.assertEqual(str(group), "doors")
        group.delete()
        door.refresh_from_db()
        self.assertIsNone(door.repeat_group_id)

    def test_repeat_index_is_null_unless_a_copy_is_named(self):
        door = question(self.request, "door-type")
        self.assertIsNone(answer(door, "Solid").repeat_index)
        self.assertEqual(answer(door, "Solid", repeat_index=2).repeat_index, 2)
        self.assertEqual(get_input_model().objects.filter(repeat_index__isnull=True).count(), 1)

    def test_a_condition_gates_an_instrument_or_a_group_never_both_nor_neither(self):
        group = repeat_group(self.request)
        door = question(self.request, "door-type")
        condition_group = factories.ConditionGroupFactory.create()
        Condition.objects.create(
            instrument=door, condition_group=condition_group, data_getter="instrument:x"
        )
        Condition.objects.create(
            repeat_group=group, condition_group=condition_group, data_getter="instrument:x"
        )
        for kwargs in ({}, {"instrument": door, "repeat_group": group}):
            with self.subTest(kwargs=kwargs):
                with transaction.atomic(), self.assertRaises(IntegrityError):
                    Condition.objects.create(
                        condition_group=condition_group, data_getter="instrument:x", **kwargs
                    )
        self.assertEqual(group.conditions.count(), 1)

    def test_a_group_condition_resolves_against_its_anchor(self):
        group = repeat_group(self.request)
        door = in_group(question(self.request, "door-type"), group)
        condition = Condition.objects.create(
            repeat_group=group,
            condition_group=factories.ConditionGroupFactory.create(),
            data_getter="debug:{'data': [1]}",
        )
        with self.assertRaises(ValueError):
            condition.resolve()
        _resolver, data, error = condition.resolve(anchor=door)
        self.assertIsNone(error)
        self.assertEqual(data, {"data": [1]})
        self.assertIn("doors", str(condition))
