"""clone_collection_request copies repeat groups, membership and conditions."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.test import TestCase

from ..collection.merge import merge_requests
from ..models.utils import clone_collection_request
from . import factories
from .checklists import question
from .repeats import answer, doors, group_gate
from .test_merge import coop


class CloneRepeatGroupTests(TestCase):
    def setUp(self):
        self.request, self.group, self.found = doors(label="Door {n}", max_count=7)
        self.has_doors = question(
            self.request, "has-doors", group="Doors", order=0, responses=("yes", "no")
        )

    def test_a_groups_are_cloned(self):
        cloned = clone_collection_request(self.request)
        group = cloned.repeat_groups.get()
        self.assertNotEqual(group.pk, self.group.pk)
        self.assertEqual(
            (group.slug, group.name, group.count_source, group.max_count, group.label, group.order),
            ("doors", "Doors", "instrument:door-count", 7, "Door {n}", 0),
        )
        self.assertEqual(list(self.request.repeat_groups.all()), [self.group])  # original intact

    def test_b_cloned_instruments_point_at_the_cloned_group(self):
        cloned = clone_collection_request(self.request)
        group = cloned.repeat_groups.get()
        members = cloned.collectioninstrument_set.filter(repeat_group=group).order_by("order")
        self.assertEqual(
            [i.measure_id for i in members], ["door-type", "door-glazed", "door-glazing-area"]
        )
        loose = cloned.collectioninstrument_set.filter(repeat_group__isnull=True)
        self.assertEqual(
            sorted(loose.values_list("measure_id", flat=True)),
            ["after-doors", "door-count", "has-doors"],
        )
        self.assertEqual(self.group.instruments.count(), 3)  # the original's still point home

    def test_c_group_conditions_are_cloned_onto_the_cloned_group(self):
        group_gate(self.group, "has-doors")  # by measure: kept as written
        group_gate(self.group, str(self.has_doors.pk))  # by pk: rewritten to the clone's pk
        cloned = clone_collection_request(self.request)
        group = cloned.repeat_groups.get()
        cloned_has_doors = cloned.collectioninstrument_set.get(measure_id="has-doors")
        conditions = list(group.conditions.order_by("pk"))
        self.assertEqual(
            [c.data_getter for c in conditions],
            ["instrument:has-doors", f"instrument:{cloned_has_doors.pk}"],
        )
        self.assertTrue(all(c.instrument_id is None for c in conditions))
        self.assertEqual(self.group.conditions.count(), 2)  # the original's untouched

    def test_a_cloned_request_still_expands_copies(self):
        group_gate(self.group, "has-doors")
        cloned = clone_collection_request(self.request)
        answer(cloned.collectioninstrument_set.get(measure_id="has-doors"), "yes")
        answer(cloned.collectioninstrument_set.get(measure_id="door-count"), "2")
        merged = merge_requests([cloned], collectors=coop(cloned))
        self.assertEqual(
            [q.key for s in merged.sections for q in s.questions if q.repeat],
            [
                "door-type#1",
                "door-glazed#1",
                "door-glazing-area#1",
                "door-type#2",
                "door-glazed#2",
                "door-glazing-area#2",
            ],
        )
        self.assertEqual(merged.groups["doors"].group.collection_request_id, cloned.pk)
        self.assertEqual(merged.questions["door-type#2"].repeat.label, "Door 2")


class CloneInstrumentConditionTests(TestCase):
    """An instrument condition's ``instrument:<pk>`` names its *gate*, not its own instrument."""

    def condition(self, child, getter):
        case = factories.CaseFactory.create(match_type="match", match_data="yes")
        condition_group = factories.ConditionGroupFactory.create(
            requirement_type="all-pass", cases=[case]
        )
        return factories.ConditionFactory.create(
            instrument=child, condition_group=condition_group, data_getter=getter
        )

    def test_pk_getter_points_at_the_cloned_gate_not_the_cloned_child(self):
        request = factories.CollectionRequestFactory.create()
        gate_instrument = question(request, "gate", order=0)
        child = question(request, "child", order=1)
        self.condition(child, f"instrument:{gate_instrument.pk}")

        cloned = clone_collection_request(request)

        cloned_gate = cloned.collectioninstrument_set.get(measure_id="gate")
        cloned_child = cloned.collectioninstrument_set.get(measure_id="child")
        condition = cloned_child.conditions.get()
        self.assertEqual(condition.data_getter, f"instrument:{cloned_gate.pk}")
        self.assertNotEqual(condition.data_getter, f"instrument:{cloned_child.pk}")
        self.assertEqual(child.conditions.get().data_getter, f"instrument:{gate_instrument.pk}")

    def test_gate_cloned_after_its_child_still_remaps(self):
        request = factories.CollectionRequestFactory.create()
        child = question(request, "child", order=0)  # cloned first
        gate_instrument = question(request, "gate", order=1)  # cloned second
        self.assertLess(child.pk, gate_instrument.pk)
        self.condition(child, f"instrument:{gate_instrument.pk}")

        cloned = clone_collection_request(request)

        cloned_gate = cloned.collectioninstrument_set.get(measure_id="gate")
        cloned_child = cloned.collectioninstrument_set.get(measure_id="child")
        self.assertEqual(cloned_child.conditions.get().data_getter, f"instrument:{cloned_gate.pk}")

    def test_measure_getter_is_unchanged(self):
        request = factories.CollectionRequestFactory.create()
        question(request, "gate", order=0)
        child = question(request, "child", order=1)
        self.condition(child, "instrument:gate")

        cloned = clone_collection_request(request)

        cloned_child = cloned.collectioninstrument_set.get(measure_id="child")
        self.assertEqual(cloned_child.conditions.get().data_getter, "instrument:gate")


class CloneQueryCountTests(TestCase):
    """A clone reads and inserts each kind of row in bulk, so its cost is flat in checklist size."""

    def queries_to_clone(self, size):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from .checklists import build_checklist

        request = factories.CollectionRequestFactory.create()
        build_checklist(size, collection_request=request, prefix=f"s{size}", answer=False)
        with CaptureQueriesContext(connection) as queries:
            cloned = clone_collection_request(request)
        self.assertEqual(
            cloned.collectioninstrument_set.count(), request.collectioninstrument_set.count()
        )
        return len(queries)

    def test_a_bigger_checklist_costs_no_more_queries(self):
        self.assertEqual(self.queries_to_clone(3), self.queries_to_clone(12))

    def test_bound_responses_and_conditions_follow_their_instrument(self):
        from .checklists import build_checklist

        request = factories.CollectionRequestFactory.create()
        build_checklist(4, collection_request=request, prefix="b", answer=False)
        cloned = clone_collection_request(request)
        for original in request.collectioninstrument_set.order_by("measure_id"):
            copy = cloned.collectioninstrument_set.get(measure_id=original.measure_id)
            self.assertEqual(
                list(
                    copy.bound_suggested_responses.values_list("suggested_response_id", flat=True)
                ),
                list(
                    original.bound_suggested_responses.values_list(
                        "suggested_response_id", flat=True
                    )
                ),
            )
            self.assertEqual(copy.conditions.count(), original.conditions.count())
