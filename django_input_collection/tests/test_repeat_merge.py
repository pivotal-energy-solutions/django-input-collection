"""merge_requests with repeat groups: expansion, order, per-copy visibility, progress, payload."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from types import SimpleNamespace
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection.exceptions import UnknownRepeatSource
from ..collection.merge import filter_per_copy, merge_requests
from ..collection.repeat import Copy
from ..managers import CollectedInputQuerySet
from ..models import get_input_model
from ..schema.merged import merged_checklist_payload
from ..schema.mixins import ChecklistConsumerMixin
from . import factories
from .checklists import gate, question
from .repeats import answer, doors, group_gate, in_group, repeat_group
from .test_cross_request_conditions import Cooperative
from .test_merge import coop
from .test_repeat_scoping import user_latest_filter_for_context


def merge(request, cls=Cooperative):
    collectors_ = coop(request, cls=cls)
    return merge_requests([request], collectors=collectors_), collectors_


def order(merged):
    return [q.key for s in merged.sections for q in s.questions]


class BoundSystems(Cooperative):
    """Binds simulation-set copies to ``systems`` and unwraps {"input": ...} like axis does."""

    __noregister__ = True
    systems = ()

    def _resolve_repeat(self, group):
        if group.count_source.startswith("simulation-set:"):
            copies = [
                Copy(n, f"System {n}", binding=system)
                for n, system in enumerate(self.systems, start=1)
            ]
            return copies, False
        return super()._resolve_repeat(group)

    def extract_data_input(self, data):
        return data["input"] if isinstance(data, dict) and "input" in data else data


class ExpansionTests(TestCase):
    def test_copies_sit_copy_major_where_the_group_sits(self):
        request, group, _found = doors(count=2, label="Door {n}")
        merged, _ = merge(request)
        self.assertEqual(
            order(merged),
            [
                "door-count",
                "door-type#1",
                "door-glazed#1",
                "door-glazing-area#1",
                "door-type#2",
                "door-glazed#2",
                "door-glazing-area#2",
                "after-doors",
            ],
        )
        info = merged.questions["door-glazed#2"].repeat
        self.assertEqual(
            (info.group_slug, info.group_id, info.index, info.count, info.label, info.first),
            ("doors", group.pk, 2, 2, "Door 2", False),
        )
        self.assertTrue(merged.questions["door-type#2"].repeat.first)
        self.assertEqual(merged.questions["door-type#1"].measure_id, "door-type")
        self.assertNotIn("door-type", merged.questions)
        self.assertIsNone(merged.questions["door-count"].repeat)

    def test_zero_or_unanswered_count_asks_nothing(self):
        for count in (None, 0):
            with self.subTest(count=count):
                merged, _ = merge(doors(count=count)[0])
                self.assertEqual(order(merged), ["door-count", "after-doors"])
                self.assertEqual(merged.groups["doors"].copies, [])

    def test_the_count_is_clamped(self):
        merged, _ = merge(doors(count=9, max_count=3)[0])
        state = merged.groups["doors"]
        self.assertEqual([c.index for c in state.copies], [1, 2, 3])
        self.assertTrue(state.clamped)
        self.assertEqual(merged.questions["door-type#3"].repeat.count, 3)

    def test_group_conditions_force_zero_copies(self):
        request, group, _found = doors(count=2)
        has_doors = question(request, "has-doors", group="Doors", order=0, responses=("yes", "no"))
        group_gate(group, "has-doors")
        self.assertEqual(merge(request)[0].groups["doors"].copies, [])
        answer(has_doors, "yes")
        self.assertEqual(len(merge(request)[0].groups["doors"].copies), 2)

    def test_each_copy_has_its_own_answer(self):
        request, _group, found = doors(count=2)
        answer(found["door-type"], "Solid", repeat_index=1)
        answer(found["door-type"], "Full-lite", repeat_index=2)
        answer(found["door-type"], "Solid", repeat_index=3)  # past N: kept, never shown
        merged, _ = merge(request)
        self.assertEqual(merged.questions["door-type#1"].answer.data, "Solid")
        self.assertEqual(merged.questions["door-type#2"].answer.data, "Full-lite")
        self.assertEqual([r.data for r in merged.questions["door-type#2"].answers], ["Full-lite"])
        self.assertNotIn("door-type#3", merged.questions)
        self.assertIn("door-type#3", merged.answers)

    def test_hidden_copies_come_back_when_the_count_rises(self):
        request, _group, found = doors(count=1)
        answer(found["door-type"], "Full-lite", repeat_index=2)
        self.assertNotIn("door-type#2", merge(request)[0].questions)
        answer(found["door-count"], "2")
        self.assertEqual(merge(request)[0].questions["door-type#2"].answer.data, "Full-lite")

    def test_an_unknown_source_raises_when_the_merge_is_built(self):
        request = doors(count_source="simulation-set:x")[0]
        with self.assertRaises(UnknownRepeatSource):
            merge(request)


class CopyVisibilityTests(TestCase):
    def test_a_sibling_gate_reads_its_own_copy(self):
        request, _group, found = doors(count=3)
        answer(found["door-glazed"], "no", repeat_index=1)
        answer(found["door-glazed"], "yes", repeat_index=2)
        visibility = merge(request)[0].evaluate()
        self.assertEqual(
            [visibility[f"door-glazing-area#{n}"] for n in (1, 2, 3)], [False, True, False]
        )
        self.assertTrue(visibility["door-type#3"])

    def test_bound_conditions_read_each_copys_object(self):
        request = factories.CollectionRequestFactory.create()
        group = repeat_group(
            request,
            slug="duct-systems",
            count_source="simulation-set:forced_air_distribution_systems",
            name="Duct systems",
        )
        in_group(question(request, "duct-result", group="Ducts", order=1), group)
        reason = in_group(question(request, "few-returns-reason", group="Ducts", order=2), group)
        case = factories.CaseFactory.create(match_type="less_than", match_data="2")
        condition_group = factories.ConditionGroupFactory.create(
            requirement_type="all-pass", cases=[case]
        )
        factories.ConditionFactory.create(
            instrument=reason,
            condition_group=condition_group,
            data_getter="bound:qty_return_grills",
        )
        collectors_ = coop(request, cls=BoundSystems)
        collectors_[request.pk].systems = [SimpleNamespace(qty_return_grills=g) for g in (1, 3, 1)]
        merged = merge_requests([request], collectors=collectors_)
        visibility = merged.evaluate()
        self.assertEqual(
            [visibility[f"few-returns-reason#{n}"] for n in (1, 2, 3)], [True, False, True]
        )
        self.assertEqual(merged.questions["duct-result#2"].repeat.binding.qty_return_grills, 3)
        self.assertEqual(merged.questions["duct-result#2"].repeat.label, "System 2")

    def test_progress_counts_live_copies(self):
        request, _group, found = doors(count=2)
        answer(found["door-type"], "Solid", repeat_index=1)
        answer(found["door-type"], "Solid", repeat_index=5)  # hidden copy: not counted
        merged, _ = merge(request)
        progress = merged.progress(merged.evaluate())
        self.assertEqual(progress["total"], 8)  # door-count, after-doors, 3 questions x 2 copies
        self.assertEqual(progress["answered"], 2)  # door-count and door-type#1
        self.assertEqual(progress["visible"], 6)  # both glazing-area copies are hidden


class RepeatPayloadTests(TestCase):
    def test_questions_carry_key_and_repeat(self):
        request, _group, _found = doors(count=2, label="Door {n}")
        merged, collectors_ = merge(request)
        payload = merged_checklist_payload(merged, collectors=collectors_)
        questions = [q for s in payload["sections"] for q in s["questions"]]
        self.assertEqual([q["key"] for q in questions[:2]], ["door-count", "door-type#1"])
        by_key = {q["key"]: q for q in questions}
        self.assertIsNone(by_key["door-count"]["repeat"])
        self.assertEqual(
            by_key["door-type#2"]["repeat"],
            {"group": "doors", "index": 2, "count": 2, "label": "Door 2", "first": True},
        )
        self.assertEqual(by_key["door-glazed#2"]["measure_id"], "door-glazed")
        self.assertFalse(by_key["door-glazed#2"]["repeat"]["first"])
        self.assertEqual(payload["progress"]["total"], 8)


class RepeatQueryTests(TestCase):
    def count(self, copies, group_condition=False):
        request, group, _found = doors(count=copies, max_count=20)
        if group_condition:
            has_doors = question(request, "has-doors", group="Doors", order=0)
            answer(has_doors, "yes")
            group_gate(group, "has-doors")
        collectors_ = coop(request)
        with CaptureQueriesContext(connection) as queries:
            merged = merge_requests([request], collectors=collectors_)
            merged.progress(merged.evaluate())
        return len(queries)

    def test_queries_do_not_grow_with_copies(self):
        self.assertEqual(self.count(2), self.count(12))
        self.assertEqual(self.count(2, group_condition=True), self.count(12, group_condition=True))

    def test_queries_do_not_grow_from_two_to_five_copies(self):
        self.assertEqual(self.count(2), self.count(5))
        self.assertEqual(self.count(2, group_condition=True), self.count(5, group_condition=True))

    def test_evaluating_copies_reads_nothing_more(self):
        request, group, found = doors(count=3)
        has_doors = question(request, "has-doors", group="Doors", order=0)
        answer(has_doors, "yes")
        group_gate(group, "has-doors")
        answer(found["door-glazed"], "yes", repeat_index=2)
        merged = merge_requests([request], collectors=coop(request))
        with self.assertNumQueries(0):
            visibility = merged.evaluate()
            merged.progress(visibility)
        self.assertEqual(
            [visibility[f"door-glazing-area#{n}"] for n in (1, 2, 3)], [False, True, False]
        )

    def test_one_group_object_is_shared_by_its_instruments(self):
        request, _group, _found = doors(count=2)
        merged, _ = merge(request)
        groups = {id(q.instrument.repeat_group) for q in merged.questions.values() if q.repeat}
        self.assertEqual(groups, {id(merged.groups["doors"].group)})

    def test_a_write_copy_collector_reads_like_a_plain_one(self):
        request, _group, _found = doors(count=2)

        def count(**context):
            collectors_ = {request.pk: Cooperative(request, **context)}
            with CaptureQueriesContext(connection) as queries:
                merge_requests([request], collectors=collectors_).evaluate()
            return len(queries)

        self.assertEqual(count(repeat_index=2), count())


class Filtering(Cooperative):
    """Overrides filter_condition_inputs, so condition reads go through filter_for_context."""

    __noregister__ = True

    def filter_condition_inputs(self, queryset):
        return queryset


class TwoRequestTests(TestCase):
    """axis merges one cloned request per program, each with its own same-slug RepeatGroup row."""

    def setUp(self):
        self.a, self.group_a, self.found_a = doors(count=2)
        self.b, self.group_b, self.found_b = doors()
        self.assertNotEqual(self.group_a.pk, self.group_b.pk)

    def test_copies_expand_once_per_key(self):
        merged = merge_requests([self.a, self.b], collectors=coop(self.a, self.b))
        self.assertEqual(
            order(merged),
            [
                "door-count",
                "door-type#1",
                "door-glazed#1",
                "door-glazing-area#1",
                "door-type#2",
                "door-glazed#2",
                "door-glazing-area#2",
                "after-doors",
            ],
        )
        self.assertEqual(list(merged.groups), ["doors"])
        self.assertEqual(merged.groups["doors"].group.pk, self.group_a.pk)
        self.assertEqual(
            merged.questions["door-type#1"].instruments,
            (self.found_a["door-type"], self.found_b["door-type"]),
        )

    def test_sibling_gates_scope_per_copy_across_requests(self):
        answer(self.found_a["door-glazed"], "no", repeat_index=1)
        answer(self.found_b["door-glazed"], "yes", repeat_index=2)  # the other request's copy 2
        merged = merge_requests([self.a, self.b], collectors=coop(self.a, self.b))
        visibility = merged.evaluate()
        self.assertEqual([visibility[f"door-glazing-area#{n}"] for n in (1, 2)], [False, True])


class LatestPerInstrumentIndexTests(TestCase):
    """The index path under a latest-row-per-instrument filter_for_context keeps every copy."""

    def setUp(self):
        self.request, self.group, self.found = doors(count=2)
        answer(self.found["door-glazed"], "yes", repeat_index=1)
        answer(self.found["door-glazed"], "no", repeat_index=2)  # newest row of the instrument

    def patched(self):
        return mock.patch.object(
            CollectedInputQuerySet, "filter_for_context", user_latest_filter_for_context
        )

    def test_merge_index_reads_each_copys_latest_row(self):
        with self.patched():
            merged = merge_requests([self.request], collectors=coop(self.request, cls=Filtering))
            visibility = merged.evaluate()
        self.assertEqual([visibility[f"door-glazing-area#{n}"] for n in (1, 2)], [True, False])
        self.assertTrue(visibility["door-type#1"])

    def test_mixin_index_reads_the_write_copys_latest_row(self):
        def shown(n):
            payload = ChecklistConsumerMixin()._build_checklist_response(
                self.request, Filtering(self.request, repeat_index=n), None, "rater"
            )
            return {
                q["measure_id"]: q["is_visible"]
                for s in payload["sections"]
                for q in s["questions"]
            }["door-glazing-area"]

        with self.patched():
            self.assertEqual([shown(n) for n in (1, 2)], [True, False])


class OwnerInvariantTests(TestCase):
    def test_every_copy_shows_its_measures_owner(self):
        a, _group, _found = doors(count=3)
        b, _group_b, _found_b = doors()
        merged = merge_requests([a, b], collectors=coop(a, b))
        for measure_id in ("door-type", "door-glazed", "door-glazing-area"):
            owners = {merged.questions[f"{measure_id}#{n}"].instrument for n in (1, 2, 3)}
            self.assertEqual(len(owners), 1, measure_id)


class FilterPerCopyTests(TestCase):
    def setUp(self):
        _request, _group, found = doors(count=2)
        self.one = answer(found["door-type"], "Solid", repeat_index=1)
        self.two = answer(found["door-type"], "Full-lite", repeat_index=2)
        self.rows = list(get_input_model().objects.order_by("date_created", "id"))

    def test_keeps_unrepeated_rows_and_the_given_copies(self):
        found = filter_per_copy(get_input_model().objects.all(), {}, {1})
        self.assertEqual(found, [row for row in self.rows if row != self.two])

    def test_without_indices_filters_once(self):
        self.assertEqual(filter_per_copy(get_input_model().objects.all(), {}), self.rows)

    def test_partitions_that_cannot_be_combined_are_read_one_by_one(self):
        with self.assertNumQueries(3):
            found = filter_per_copy(
                get_input_model().objects.all(), {}, {1, 2}, narrow=lambda qs: qs.union(qs)
            )
        self.assertEqual(found, self.rows)


class DependentsTests(TestCase):
    def setUp(self):
        self.request, self.group, self.found = doors(count=2)
        self.merged = merge(self.request)[0]

    def test_a_copy_reaches_its_own_siblings_only(self):
        self.assertEqual(self.merged.dependents("door-glazed#2"), ["door-glazing-area#2"])
        self.assertEqual(self.merged.dependents("door-type#1"), [])

    def test_the_count_reaches_every_copy(self):
        expected = sorted(
            f"{measure}#{n}"
            for measure in ("door-type", "door-glazed", "door-glazing-area")
            for n in (1, 2)
        )
        self.assertEqual(self.merged.dependents("door-count"), expected)
        self.assertEqual(self.merged.count_dependents("door-count"), ["doors"])
        self.assertEqual(self.merged.count_dependents("after-doors"), [])

    def test_a_group_condition_source_reaches_every_copy(self):
        answer(question(self.request, "has-doors", group="Doors", order=0), "yes")
        group_gate(self.group, "has-doors")
        merged = merge(self.request)[0]
        self.assertEqual(len(merged.dependents("has-doors")), 6)
        self.assertEqual(merged.count_dependents("has-doors"), ["doors"])

    def test_an_outside_gate_reaches_every_copy_of_its_member(self):
        question(self.request, "frame-type", group="Doors", order=0, responses=("yes", "no"))
        gate(self.found["door-type"], "frame-type")
        merged = merge(self.request)[0]
        self.assertEqual(merged.dependents("frame-type"), ["door-type#1", "door-type#2"])

    def test_a_zero_count_has_no_copies_but_still_a_dependent_group(self):
        answer(self.found["door-count"], "0")
        merged = merge(self.request)[0]
        self.assertEqual(merged.dependents("door-count"), [])
        self.assertEqual(merged.count_dependents("door-count"), ["doors"])

    def test_dependents_add_no_queries(self):
        with self.assertNumQueries(0):
            self.merged.dependents("door-count")
            self.merged.count_dependents("door-count")


class TwoRequestDependentsTests(TestCase):
    """Siblings match by group slug: each request's same-slug RepeatGroup has its own pk."""

    def test_a_copy_reaches_its_own_siblings_across_same_slug_groups(self):
        a, group_a, _found_a = doors(count=2)
        b, group_b, found_b = doors(count=2)
        self.assertNotEqual(group_a.pk, group_b.pk)

        def owner(measure_id, instruments, answer):
            # door-glazing-area shows b's instrument, so its copies carry b's group pk
            # while their gate source (door-glazed) is owned by a's group.
            return instruments[1] if measure_id == "door-glazing-area" else instruments[0]

        merged = merge_requests([a, b], collectors=coop(a, b), owner=owner)
        self.assertEqual(merged.questions["door-glazing-area#2"].repeat.group_id, group_b.pk)
        self.assertEqual(merged.questions["door-glazed#2"].repeat.group_id, group_a.pk)
        self.assertEqual(merged.dependents("door-glazed#2"), ["door-glazing-area#2"])
        self.assertEqual(merged.count_dependents("door-count"), ["doors"])
