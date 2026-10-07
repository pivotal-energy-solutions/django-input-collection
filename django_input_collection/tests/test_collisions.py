"""Shared measures must be the same question wherever they are asked."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..models import CollectionRequest
from ..schema.builder import CollectionRequestBuilder
from ..schema.collisions import (
    MeasureCollisionError,
    MeasureSignature,
    check_measure_collisions,
    find_measure_collisions,
    normalize_flags,
    signatures_for_request,
    signatures_from_schema,
)
from .checklists import question


def sig(**overrides):
    base = dict(
        type="multiple-choice",
        responses=("Yes", "No"),
        response_flags=(),
        required=True,
        text="Q?",
        provides_for=(),
        description="d",
        help="h",
    )
    return MeasureSignature(**{**base, **overrides})


class FindTests(TestCase):
    def test_identical_and_description_only_do_not_collide(self):
        others = {"b": {"m": sig(description="other", help="other")}}
        self.assertEqual(find_measure_collisions("a", {"m": sig()}, others), [])

    def test_each_compared_field(self):
        cases = {
            "type": sig(type="open"),
            "responses": sig(responses=("No", "Yes")),  # order matters
            "response_flags": sig(response_flags=(("No", (("comment_required", True),)),)),
            "required": sig(required=False),
            "text": sig(text="Other?"),
            "provides_for": sig(provides_for=("simulation.simulation",)),
        }
        for field_name, other in cases.items():
            with self.subTest(field_name):
                (found,) = find_measure_collisions("a", {"m": sig()}, {"b": {"m": other}})
                self.assertEqual(list(found.differences), [field_name])
                self.assertEqual((found.subject, found.other), ("a", "b"))

    def test_skip(self):
        others = {"b": {"m": sig(required=False)}}
        self.assertEqual(
            find_measure_collisions("a", {"m": sig()}, others, skip=lambda s, o: True), []
        )

    def test_subject_is_never_compared_with_itself_and_unshared_measures_are_ignored(self):
        others = {"a": {"m": sig(text="x")}, "b": {"n": sig(text="y")}}
        self.assertEqual(find_measure_collisions("a", {"m": sig()}, others), [])


class NormalizeTests(TestCase):
    def test_flag_order_falsy_flags_and_empties(self):
        a = {"No": {"photo_required": True, "comment_required": True}, "Yes": {}}
        b = {"No": {"comment_required": True, "photo_required": True, "document_required": False}}
        self.assertEqual(normalize_flags(a), normalize_flags(b))
        self.assertEqual(normalize_flags(None), ())
        self.assertEqual(normalize_flags({"Yes": None}), ())

    def test_provides_for_none_missing_and_string(self):
        schema = {
            "sections": [
                {
                    "name": "S",
                    "questions": [
                        {"measure_id": "a", "text": "A", "context": None},
                        {"measure_id": "b", "text": "B", "context": {"provides_for": None}},
                        {"measure_id": "c", "text": "C"},
                        {"measure_id": "d", "text": "D", "context": {"provides_for": "x.y"}},
                    ],
                }
            ]
        }
        found = signatures_from_schema(schema)
        self.assertEqual({found[m].provides_for for m in "abc"}, {()})
        self.assertEqual(found["d"].provides_for, ("x.y",))


class CheckTests(TestCase):
    def test_severity_splits_errors_and_warnings(self):
        others = {"active": {"m": sig(text="x")}, "legacy": {"m": sig(text="y")}}
        report = check_measure_collisions(
            "a",
            {"m": sig()},
            others,
            severity=lambda c: "error" if c.other == "active" else "warning",
        )
        self.assertEqual([c.other for c in report.errors], ["active"])
        self.assertEqual([c.other for c in report.warnings], ["legacy"])
        with self.assertRaises(MeasureCollisionError) as raised:
            report.raise_for_errors()
        self.assertIn("m", str(raised.exception))
        self.assertIn("text", str(raised.exception))
        self.assertEqual(raised.exception.collisions, report.errors)

    def test_severity_none_ignores(self):
        report = check_measure_collisions(
            "a", {"m": sig()}, {"b": {"m": sig(text="x")}}, severity=lambda c: None
        )
        self.assertEqual((report.errors, report.warnings), ([], []))
        report.raise_for_errors()


class ProducerTests(TestCase):
    SCHEMA = {
        "sections": [
            {
                "name": "S",
                "questions": [
                    {
                        "measure_id": "m",
                        "text": "Q?",
                        "type": "multiple-choice",
                        "responses": ["Yes", "No", "Maybe"],
                        "response_flags": {"No": {"comment_required": True}},
                        "context": {"provides_for": ["simulation.simulation"]},
                    }
                ],
            }
        ]
    }

    def test_schema_and_built_request_agree(self):
        built = CollectionRequestBuilder().build(self.SCHEMA)
        from_schema = signatures_from_schema(self.SCHEMA)["m"]
        from_request = signatures_for_request(built)["m"]
        # demo BoundSuggestedResponse has no flag fields, so flags are not compared here
        for name in ("type", "responses", "required", "text", "provides_for"):
            with self.subTest(name):
                self.assertEqual(getattr(from_schema, name), getattr(from_request, name))

    def test_builder_refuses_before_writing(self):
        before = CollectionRequest.objects.count()

        def check(signatures):
            return check_measure_collisions(
                "new",
                signatures,
                {"old": {"m": sig(text="Different?")}},
                severity=lambda c: "error",
            )

        with self.assertRaises(MeasureCollisionError):
            CollectionRequestBuilder().build(self.SCHEMA, collision_check=check)
        self.assertEqual(CollectionRequest.objects.count(), before)

    def test_builder_records_warnings_and_builds(self):
        def check(signatures):
            return check_measure_collisions(
                "new",
                signatures,
                {"old": {"m": sig(text="Different?")}},
                severity=lambda c: "warning",
            )

        builder = CollectionRequestBuilder()
        built = builder.build(self.SCHEMA, collision_check=check)
        self.assertEqual(built.collectioninstrument_set.count(), 1)
        self.assertEqual(len(builder.warnings), 1)
        self.assertIn("text", builder.warnings[0])

    def _count(self, size):
        request = CollectionRequest.objects.create()
        for n in range(size):
            question(request, f"z{size}-{n}", responses=("a", "b"))
        with CaptureQueriesContext(connection) as captured:
            signatures_for_request(request)
        return len(captured)

    def test_signatures_for_request_query_count_is_fixed(self):
        self.assertEqual(self._count(3), self._count(9))
        request = CollectionRequest.objects.create()
        for n in range(3):
            question(request, f"z-{n}", responses=("a", "b"))
        with self.assertNumQueries(3):  # instruments+policy, bound, bound.suggested_response
            signatures = signatures_for_request(request)
        self.assertEqual(signatures["z-0"].responses, ("a", "b"))
