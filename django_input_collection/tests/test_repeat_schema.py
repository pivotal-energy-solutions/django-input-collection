"""The checklist JSON schema's repeat item: validation, build, export."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import copy
from io import StringIO

from django.test import TestCase

from ..management.commands.validate_collection_schema import Command as ValidateCommand
from ..schema.builder import CollectionRequestBuilder
from ..schema.collisions import signatures_from_schema
from ..schema.exporter import CollectionRequestExporter
from ..schema.items import iter_questions
from ..schema.serializers import CollectionSchemaSerializer, SectionSerializer

DOORS = {
    "version": "1.0",
    "name": "Doors",
    "sections": [
        {
            "name": "Doors",
            "questions": [
                {
                    "measure_id": "has-doors",
                    "text": "Any exterior doors?",
                    "type": "multiple-choice",
                    "responses": ["Yes", "No"],
                },
                {
                    "measure_id": "door-count",
                    "text": "How many exterior doors?",
                    "type": "integer",
                    "constraints": {"min": 0, "max": 20},
                },
                {
                    "repeat": {
                        "id": "doors",
                        "count": {"source": "instrument:door-count"},
                        "max_count": 20,
                        "label": "Door {n}",
                        "conditions": [
                            {"type": "instrument", "source": "has-doors", "values": ["Yes"]}
                        ],
                        "questions": [
                            {
                                "measure_id": "door-type",
                                "text": "Door type",
                                "type": "multiple-choice",
                                "responses": ["Solid", "Half-lite", "Full-lite"],
                            },
                            {
                                "measure_id": "door-glazed",
                                "text": "Glazed?",
                                "type": "multiple-choice",
                                "responses": ["Yes", "No"],
                            },
                            {
                                "measure_id": "door-glazing-area",
                                "text": "Glazing area (sq ft)",
                                "type": "float",
                                "conditions": [
                                    {
                                        "type": "instrument",
                                        "source": "door-glazed",
                                        "values": ["Yes"],
                                    }
                                ],
                            },
                        ],
                    }
                },
                {"measure_id": "door-notes", "text": "Notes", "type": "open", "required": False},
            ],
        }
    ],
}

BOUND_RULE = {
    "type": "bound",
    "source": "qty_return_grills",
    "match_type": "less_than",
    "values": [2],
}


def doors_schema():
    return copy.deepcopy(DOORS)


def repeat_of(schema):
    return schema["sections"][0]["questions"][2]["repeat"]


def model_driven(schema):
    """The doors group counted by a simulation set, door-glazing-area gated on a bound value."""
    repeat = repeat_of(schema)
    repeat["count"] = {"source": "simulation-set:forced_air_distribution_systems"}
    repeat["questions"][2]["conditions"] = [dict(BOUND_RULE)]
    return schema


class RepeatSerializerTests(TestCase):
    def errors(self, schema):
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())
        return str(serializer.errors)

    def test_the_doors_example_is_valid(self):
        serializer = CollectionSchemaSerializer(data=doors_schema())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        item = serializer.validated_data["sections"][0]["questions"][2]
        self.assertEqual(item["repeat"]["id"], "doors")
        self.assertEqual(item["repeat"]["count"], {"source": "instrument:door-count"})
        self.assertEqual(
            [q["measure_id"] for q in item["repeat"]["questions"]],
            ["door-type", "door-glazed", "door-glazing-area"],
        )

    def test_a_model_driven_group_with_a_bound_condition_is_valid(self):
        serializer = CollectionSchemaSerializer(data=model_driven(doors_schema()))
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_max_count_required(self):
        schema = doors_schema()
        del repeat_of(schema)["max_count"]
        self.assertIn("max_count required", self.errors(schema))

    def test_nested_repeat(self):
        schema = doors_schema()
        inner = {
            "repeat": {
                "id": "inner",
                "count": {"source": "instrument:door-count"},
                "max_count": 2,
                "questions": [{"measure_id": "inner-q", "text": "Inner"}],
            }
        }
        repeat_of(schema)["questions"].append(inner)
        self.assertIn("nested repeat", self.errors(schema))

    def test_count_instrument_inside_group(self):
        schema = doors_schema()
        repeat_of(schema)["count"] = {"source": "instrument:door-glazed"}
        self.assertIn("count instrument inside group", self.errors(schema))

    def test_count_instrument_not_integer(self):
        for source in ("instrument:door-notes", "instrument:nowhere"):
            with self.subTest(source=source):
                schema = doors_schema()
                repeat_of(schema)["count"] = {"source": source}
                self.assertIn("count instrument not integer", self.errors(schema))

    def test_an_unknown_count_source_kind(self):
        schema = doors_schema()
        repeat_of(schema)["count"] = {"source": "model:doors"}
        self.assertIn("count source must be", self.errors(schema))

    def test_measure_in_two_groups(self):
        schema = doors_schema()
        schema["sections"][0]["questions"].append(
            {"measure_id": "door-type", "text": "Again", "type": "open"}
        )
        self.assertIn("measure in two groups", self.errors(schema))
        schema = doors_schema()
        schema["sections"][0]["questions"].append(
            {
                "repeat": {
                    "id": "windows",
                    "count": {"source": "instrument:door-count"},
                    "max_count": 3,
                    "questions": [{"measure_id": "door-type", "text": "Again", "type": "open"}],
                }
            }
        )
        self.assertIn("measure in two groups", self.errors(schema))

    def test_outside_condition_on_repeated_measure(self):
        schema = doors_schema()
        schema["sections"][0]["questions"][3]["conditions"] = [
            {"type": "instrument", "source": "door-glazed", "values": ["Yes"]}
        ]
        self.assertIn("outside condition on repeated measure", self.errors(schema))

    def test_bound_condition_requires_simulation_set(self):
        schema = doors_schema()
        repeat_of(schema)["questions"][2]["conditions"] = [dict(BOUND_RULE)]
        self.assertIn("bound condition requires simulation-set", self.errors(schema))
        schema = doors_schema()
        schema["sections"][0]["questions"][3]["conditions"] = [dict(BOUND_RULE)]
        self.assertIn("bound condition requires simulation-set", self.errors(schema))

    def test_group_condition_uses_in_group_or_bound_source(self):
        in_group = {"type": "instrument", "source": "door-glazed", "values": ["Yes"]}
        for rule in (in_group, dict(BOUND_RULE)):
            with self.subTest(rule=rule):
                schema = model_driven(doors_schema())
                repeat_of(schema)["conditions"] = [rule]
                self.assertIn("group condition uses in-group or bound source", self.errors(schema))
        schema = doors_schema()
        repeat_of(schema)["conditions"] = [
            {
                "logic": "any",
                "rules": [
                    {"type": "instrument", "source": "has-doors", "values": ["Yes"]},
                    {"type": "instrument", "source": "door-type", "values": ["Solid"]},
                ],
            }
        ]
        self.assertIn("group condition uses in-group or bound source", self.errors(schema))

    def test_a_group_condition_on_an_unknown_measure(self):
        schema = doors_schema()
        repeat_of(schema)["conditions"] = [
            {"type": "instrument", "source": "nowhere", "values": ["Yes"]}
        ]
        self.assertIn("referencing unknown measure_id", self.errors(schema))

    def test_duplicate_repeat_ids(self):
        schema = doors_schema()
        schema["sections"][0]["questions"].append(
            {
                "repeat": {
                    "id": "doors",
                    "count": {"source": "instrument:door-count"},
                    "max_count": 3,
                    "questions": [{"measure_id": "other", "text": "Other"}],
                }
            }
        )
        self.assertIn("duplicate repeat id", self.errors(schema))

    def test_ordinary_duplicates_keep_their_message(self):
        schema = doors_schema()
        schema["sections"][0]["questions"].append({"measure_id": "door-notes", "text": "Again"})
        self.assertIn("Duplicate measure_ids found", self.errors(schema))

    def test_a_section_accepts_a_repeat_item(self):
        serializer = SectionSerializer(data=doors_schema()["sections"][0])
        self.assertTrue(serializer.is_valid(), serializer.errors)


class SchemaReaderTests(TestCase):
    def test_iter_questions_flattens_repeats(self):
        found = [
            (q["measure_id"], repeat["id"] if repeat else None)
            for q, repeat in iter_questions(doors_schema()["sections"])
        ]
        self.assertEqual(
            found,
            [
                ("has-doors", None),
                ("door-count", None),
                ("door-type", "doors"),
                ("door-glazed", "doors"),
                ("door-glazing-area", "doors"),
                ("door-notes", None),
            ],
        )

    def test_collision_signatures_include_repeated_measures(self):
        self.assertIn("door-glazing-area", signatures_from_schema(doors_schema()))

    def test_the_verbose_summary_lists_repeated_questions(self):
        serializer = CollectionSchemaSerializer(data=doors_schema())
        serializer.is_valid(raise_exception=True)
        out = StringIO()
        ValidateCommand(stdout=out)._print_summary(serializer.validated_data, True)
        self.assertIn("Questions: 6", out.getvalue())
        self.assertIn("door-glazing-area [float, required] (1 conditions)", out.getvalue())


def build(schema=None, existing=None):
    serializer = CollectionSchemaSerializer(data=schema or doors_schema())
    serializer.is_valid(raise_exception=True)
    return CollectionRequestBuilder().build(serializer.validated_data, existing)


class RepeatBuilderTests(TestCase):
    def test_groups_and_membership(self):
        request = build()
        group = request.repeat_groups.get()
        self.assertEqual(
            (group.slug, group.name, group.count_source, group.max_count, group.label, group.order),
            ("doors", "Doors", "instrument:door-count", 20, "Door {n}", 3),
        )
        members = request.collectioninstrument_set.filter(repeat_group=group).order_by("order")
        self.assertEqual(
            [i.measure_id for i in members], ["door-type", "door-glazed", "door-glazing-area"]
        )
        self.assertEqual(
            list(
                request.collectioninstrument_set.order_by("order").values_list(
                    "measure_id", flat=True
                )
            ),
            [
                "has-doors",
                "door-count",
                "door-type",
                "door-glazed",
                "door-glazing-area",
                "door-notes",
            ],
        )
        notes = request.collectioninstrument_set.get(measure_id="door-notes")
        self.assertIsNone(notes.repeat_group_id)

    def test_a_named_group(self):
        schema = doors_schema()
        repeat_of(schema)["name"] = "Exterior doors"
        self.assertEqual(build(schema).repeat_groups.get().name, "Exterior doors")

    def test_group_conditions_hang_on_the_group(self):
        request = build()
        group = request.repeat_groups.get()
        self.assertEqual([c.data_getter for c in group.conditions.all()], ["instrument:has-doors"])
        self.assertIsNone(group.conditions.get().instrument_id)
        area = request.collectioninstrument_set.get(measure_id="door-glazing-area")
        self.assertEqual([c.data_getter for c in area.conditions.all()], ["instrument:door-glazed"])

    def test_bound_conditions_store_a_bound_getter(self):
        request = build(model_driven(doors_schema()))
        area = request.collectioninstrument_set.get(measure_id="door-glazing-area")
        self.assertEqual(
            [c.data_getter for c in area.conditions.all()], ["bound:qty_return_grills"]
        )

    def test_a_rebuild_updates_and_drops_groups(self):
        request = build()
        group_pk = request.repeat_groups.get().pk
        schema = doors_schema()
        repeat_of(schema)["max_count"] = 5
        build(schema, request)
        group = request.repeat_groups.get()
        self.assertEqual((group.pk, group.max_count, group.conditions.count()), (group_pk, 5, 1))
        schema = doors_schema()
        schema["sections"][0]["questions"].pop(2)
        build(schema, request)
        self.assertFalse(request.repeat_groups.exists())


class RepeatExporterTests(TestCase):
    def export(self, schema=None):
        return CollectionRequestExporter().export(build(schema), name="Doors")

    def test_round_trip(self):
        exported = self.export()
        items = exported["sections"][0]["questions"]
        self.assertEqual(
            [item.get("measure_id") or item["repeat"]["id"] for item in items],
            ["has-doors", "door-count", "doors", "door-notes"],
        )
        repeat = items[2]["repeat"]
        self.assertEqual(repeat["count"], {"source": "instrument:door-count"})
        self.assertEqual(
            (repeat["max_count"], repeat["label"], repeat["name"]), (20, "Door {n}", "Doors")
        )
        self.assertEqual(
            repeat["conditions"],
            [
                {
                    "type": "instrument",
                    "source": "has-doors",
                    "match_type": "match",
                    "values": ["Yes"],
                }
            ],
        )
        self.assertEqual(
            [q["measure_id"] for q in repeat["questions"]],
            ["door-type", "door-glazed", "door-glazing-area"],
        )
        again = CollectionSchemaSerializer(data=exported)
        self.assertTrue(again.is_valid(), again.errors)
        rebuilt = CollectionRequestBuilder().build(again.validated_data)
        self.assertEqual(CollectionRequestExporter().export(rebuilt, name="Doors"), exported)

    def test_response_sets_reach_into_repeats(self):
        exported = self.export()
        self.assertEqual(exported["response_sets"], {"yes-no": ["Yes", "No"]})
        glazed = exported["sections"][0]["questions"][2]["repeat"]["questions"][1]
        self.assertEqual(glazed["response_set"], "yes-no")

    def test_bound_conditions_round_trip(self):
        exported = self.export(model_driven(doors_schema()))
        area = exported["sections"][0]["questions"][2]["repeat"]["questions"][2]
        self.assertEqual(area["conditions"], [dict(BOUND_RULE)])
