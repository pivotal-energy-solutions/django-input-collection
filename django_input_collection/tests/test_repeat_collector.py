"""BaseCollector.resolve_repeat / test_repeat_conditions / repeat_clamped and per-copy writes."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.test import TestCase

from ..collection import collectors
from ..collection.exceptions import UnknownRepeatSource
from ..collection.repeat import Copy, repeat_anchor
from ..collection.resolvers import read_pass
from .checklists import question
from .repeats import answer, doors, group_gate


class ResolveRepeatTests(TestCase):
    def copies(self, count=None, **group_kwargs):
        request, group, _found = doors(count=count, **group_kwargs)
        collector = collectors.Collector(request)
        return collector.resolve_repeat(group), collector, group

    def test_copies_follow_the_count_answer(self):
        copies, collector, group = self.copies(count=3)
        self.assertEqual(copies, [Copy(1, "Doors 1"), Copy(2, "Doors 2"), Copy(3, "Doors 3")])
        self.assertFalse(collector.repeat_clamped(group))

    def test_the_label_template(self):
        copies, _collector, _group = self.copies(count=2, label="Door {n}")
        self.assertEqual([c.label for c in copies], ["Door 1", "Door 2"])

    def test_no_answer_zero_negative_or_non_integer_is_no_copies(self):
        for count in (None, 0, -2, "three", "2.5"):
            with self.subTest(count=count):
                self.assertEqual(self.copies(count=count)[0], [])

    def test_the_count_is_clamped_to_max_count(self):
        copies, collector, group = self.copies(count=30, max_count=4)
        self.assertEqual([c.index for c in copies], [1, 2, 3, 4])
        self.assertTrue(collector.repeat_clamped(group))

    def test_the_newest_count_wins(self):
        request, group, found = doors(count=2)
        answer(found["door-count"], "4")
        self.assertEqual(len(collectors.Collector(request).resolve_repeat(group)), 4)

    def test_a_repeated_row_is_never_the_count(self):
        request, group, found = doors()
        answer(found["door-count"], "3", repeat_index=1)
        self.assertEqual(collectors.Collector(request).resolve_repeat(group), [])

    def test_a_write_copy_in_the_context_does_not_hide_the_count(self):
        request, group, _found = doors(count=2)
        collector = collectors.Collector(request, repeat_index=1)
        self.assertEqual(len(collector.resolve_repeat(group)), 2)

    def test_group_conditions_gate_the_whole_group(self):
        request, group, _found = doors(count=2)
        has_doors = question(request, "has-doors", group="Doors", order=0, responses=("yes", "no"))
        group_gate(group, "has-doors")
        collector = collectors.Collector(request)
        self.assertFalse(collector.test_repeat_conditions(group))
        self.assertEqual(collector.resolve_repeat(group), [])
        answer(has_doors, "yes")
        self.assertTrue(collector.test_repeat_conditions(group))
        self.assertEqual(len(collector.resolve_repeat(group)), 2)

    def test_no_group_conditions_pass(self):
        request, group, _found = doors()
        self.assertTrue(collectors.Collector(request).test_repeat_conditions(group))

    def test_an_unknown_source_raises(self):
        request, group, _found = doors(
            count_source="simulation-set:forced_air_distribution_systems"
        )
        with self.assertRaises(UnknownRepeatSource):
            collectors.Collector(request).resolve_repeat(group)

    def test_memoised_per_read_pass(self):
        request, group, _found = doors(count=2)
        collector = collectors.Collector(request)
        with read_pass():
            first = collector.resolve_repeat(group)
            with self.assertNumQueries(0):
                self.assertEqual(collector.resolve_repeat(group), first)

    def test_the_anchor_is_the_groups_first_instrument(self):
        _request, group, found = doors()
        self.assertEqual(repeat_anchor(group), found["door-type"])


class SimulationSetCollector(collectors.Collector):
    """Overrides only the extension point, as axis's ChecklistCollector does."""

    __noregister__ = True
    calls = 0

    def _resolve_repeat(self, group):
        if group.count_source.startswith("simulation-set:"):
            self.calls += 1
            return [Copy(1, "System 1"), Copy(2, "System 2")], True
        return super()._resolve_repeat(group)


class ResolveRepeatExtensionTests(TestCase):
    def test_an_override_of_resolve_repeat_internals_keeps_conditions_memo_and_clamping(self):
        request, group, _found = doors(count_source="simulation-set:systems")
        has_doors = question(request, "has-doors", group="Doors", order=0, responses=("yes", "no"))
        group_gate(group, "has-doors")
        collector = SimulationSetCollector(request)
        self.assertEqual(collector.resolve_repeat(group), [])  # conditions fail: never called
        self.assertEqual((collector.calls, collector.repeat_clamped(group)), (0, False))
        answer(has_doors, "yes")
        with read_pass():
            first = collector.resolve_repeat(group)
            self.assertEqual(collector.resolve_repeat(group), first)
        self.assertEqual([c.label for c in first], ["System 1", "System 2"])
        self.assertEqual(collector.calls, 1)  # memoised within the pass
        self.assertTrue(collector.repeat_clamped(group))


class CopyWriteTests(TestCase):
    def setUp(self):
        self.request, self.group, self.found = doors(count=2)
        self.request.max_instrument_inputs_per_user = None
        self.request.max_instrument_inputs = 1
        self.request.save()

    def instrument(self, measure):
        return self.request.collectioninstrument_set.get(measure_id=measure)

    def test_store_stamps_the_copy_from_the_context(self):
        row = collectors.Collector(self.request, repeat_index=2).store(
            self.instrument("door-type"), "Solid"
        )
        self.assertEqual(row.repeat_index, 2)
        plain = collectors.Collector(self.request).store(self.instrument("after-doors"), "x")
        self.assertIsNone(plain.repeat_index)

    def test_input_limits_apply_per_copy(self):
        door = self.instrument("door-type")
        first = collectors.Collector(self.request, repeat_index=1)
        self.assertTrue(first.is_input_allowed(door))
        first.store(door, "Solid")
        self.assertFalse(first.is_input_allowed(door))
        self.assertTrue(collectors.Collector(self.request, repeat_index=2).is_input_allowed(door))

    def test_write_availability_reads_the_same_copy(self):
        area = self.instrument("door-glazing-area")
        answer(self.found["door-glazed"], "yes", repeat_index=2)
        self.assertFalse(
            collectors.Collector(self.request, repeat_index=1).is_instrument_allowed(area)
        )
        self.assertTrue(
            collectors.Collector(self.request, repeat_index=2).is_instrument_allowed(area)
        )
