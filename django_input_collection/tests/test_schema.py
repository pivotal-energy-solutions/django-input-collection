"""test_schema.py: Tests for the schema module (serializers, builder, exporter)"""

__author__ = "Steven Klass"
__date__ = "01/08/26"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.test import TestCase

from ..schema.serializers import (
    CollectionSchemaSerializer,
    SectionSerializer,
    QuestionSerializer,
    ConditionRuleSerializer,
    QuestionConditionSerializer,
)
from ..schema.builder import CollectionRequestBuilder
from ..schema.exporter import CollectionRequestExporter
from . import factories


class SerializerValidationTests(TestCase):
    """Tests for schema serializer validation."""

    def test_valid_minimal_schema(self):
        """Test that a minimal valid schema passes validation."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Question 1",
                            "type": "open",
                        }
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_schema_with_multiple_choice(self):
        """Test schema with multiple choice question and responses."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Yes or No?",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                        }
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_schema_with_response_sets(self):
        """Test schema using response_sets for shared responses."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "response_sets": {"yes-no": ["Yes", "No"]},
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "First question",
                            "type": "multiple-choice",
                            "response_set": "yes-no",
                        },
                        {
                            "measure_id": "q2",
                            "text": "Second question",
                            "type": "multiple-choice",
                            "response_set": "yes-no",
                        },
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_schema_with_conditions(self):
        """Test schema with instrument conditions."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Yes or No?",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                        },
                        {
                            "measure_id": "q2",
                            "text": "Follow up",
                            "type": "open",
                            "conditions": [
                                {
                                    "type": "instrument",
                                    "source": "q1",
                                    "match_type": "match",
                                    "values": ["Yes"],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_schema_with_response_flags(self):
        """Test schema with response flags (comment_required, photo_required, etc.)."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Question with flags",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No", "N/A"],
                            "response_flags": {
                                "No": {"comment_required": True},
                                "N/A": {"document_required": True},
                            },
                        }
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_schema_empty_sections(self):
        """Test that schema with no sections fails validation."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())
        self.assertIn("sections", serializer.errors)

    def test_invalid_schema_empty_questions(self):
        """Test that section with no questions fails validation."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [{"name": "Empty Section", "questions": []}],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())

    def test_invalid_schema_duplicate_measure_ids(self):
        """Test that duplicate measure_ids fail validation."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {"measure_id": "q1", "text": "Question 1", "type": "open"},
                        {"measure_id": "q1", "text": "Duplicate ID", "type": "open"},
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())
        self.assertIn("sections", serializer.errors)
        self.assertIn("Duplicate", str(serializer.errors["sections"]))

    def test_invalid_schema_unknown_condition_source(self):
        """Test that condition referencing unknown measure_id fails."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Question",
                            "type": "open",
                            "conditions": [
                                {
                                    "type": "instrument",
                                    "source": "nonexistent",
                                    "match_type": "match",
                                    "values": ["Yes"],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())
        self.assertIn("sections", serializer.errors)

    def test_invalid_schema_unknown_response_set(self):
        """Test that referencing unknown response_set fails."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Question",
                            "type": "multiple-choice",
                            "response_set": "nonexistent",
                        }
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())

    def test_invalid_schema_multiple_choice_without_responses(self):
        """Test that multiple-choice without responses fails."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Question",
                            "type": "multiple-choice",
                        }
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())

    def test_invalid_condition_values_for_source(self):
        """Test that condition values must match source question's responses."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Yes or No?",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                        },
                        {
                            "measure_id": "q2",
                            "text": "Follow up",
                            "type": "open",
                            "conditions": [
                                {
                                    "type": "instrument",
                                    "source": "q1",
                                    "match_type": "match",
                                    "values": ["Maybe"],  # Invalid - not in q1's responses
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertFalse(serializer.is_valid())
        self.assertIn("sections", serializer.errors)
        self.assertIn("invalid values", str(serializer.errors["sections"]).lower())

    def test_condition_values_case_insensitive(self):
        """Test that condition values are validated case-insensitively."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Yes or No?",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                        },
                        {
                            "measure_id": "q2",
                            "text": "Follow up",
                            "type": "open",
                            "conditions": [
                                {
                                    "type": "instrument",
                                    "source": "q1",
                                    "match_type": "match",
                                    "values": ["yes"],  # lowercase should match "Yes"
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        serializer = CollectionSchemaSerializer(data=schema)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class SectionSerializerTests(TestCase):
    """Tests for SectionSerializer - no description field."""

    def test_section_without_description(self):
        """Test that section works without description field."""
        section = {
            "name": "Test Section",
            "questions": [{"measure_id": "q1", "text": "Question", "type": "open"}],
        }
        serializer = SectionSerializer(data=section)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # Ensure description is not in validated data
        self.assertNotIn("description", serializer.validated_data)

    def test_section_with_slug(self):
        """Test section with custom slug."""
        section = {
            "name": "Test Section",
            "slug": "custom-slug",
            "questions": [{"measure_id": "q1", "text": "Question", "type": "open"}],
        }
        serializer = SectionSerializer(data=section)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["slug"], "custom-slug")


class QuestionSerializerTests(TestCase):
    """Tests for QuestionSerializer."""

    def test_question_with_constraints(self):
        """Test numeric question with min/max constraints."""
        question = {
            "measure_id": "q1",
            "text": "Enter a number",
            "type": "integer",
            "constraints": {"min": 0, "max": 100},
        }
        serializer = QuestionSerializer(data=question)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_question_invalid_constraints_for_type(self):
        """Test that numeric constraints fail for multiple-choice."""
        question = {
            "measure_id": "q1",
            "text": "Choose one",
            "type": "multiple-choice",
            "responses": ["A", "B"],
            "constraints": {"min": 0},  # Invalid for multiple-choice
        }
        serializer = QuestionSerializer(data=question)
        self.assertFalse(serializer.is_valid())
        self.assertIn("constraints", serializer.errors)

    def test_question_invalid_response_flags_key(self):
        """Test that response_flags with invalid key fails."""
        question = {
            "measure_id": "q1",
            "text": "Question",
            "type": "multiple-choice",
            "responses": ["Yes", "No"],
            "response_flags": {
                "Maybe": {"comment_required": True}  # Invalid - not in responses
            },
        }
        serializer = QuestionSerializer(data=question)
        self.assertFalse(serializer.is_valid())
        self.assertIn("response_flags", serializer.errors)


class ConditionSerializerTests(TestCase):
    """Tests for condition serializers."""

    def test_simple_condition_format(self):
        """Test simple condition format."""
        condition = {
            "type": "instrument",
            "source": "q1",
            "match_type": "match",
            "values": ["Yes"],
        }
        serializer = QuestionConditionSerializer(data=condition)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["_format"], "simple")

    def test_group_condition_format(self):
        """Test group condition format with logic."""
        condition = {
            "logic": "any",
            "rules": [
                {"type": "instrument", "source": "q1", "match_type": "match", "values": ["Yes"]},
                {"type": "instrument", "source": "q2", "match_type": "match", "values": ["No"]},
            ],
        }
        serializer = QuestionConditionSerializer(data=condition)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["_format"], "group")
        self.assertEqual(serializer.validated_data["logic"], "any")

    def test_invalid_mixed_format(self):
        """Test that mixing simple and group format fails."""
        condition = {
            "type": "instrument",
            "source": "q1",
            "logic": "any",
            "rules": [],
        }
        serializer = QuestionConditionSerializer(data=condition)
        self.assertFalse(serializer.is_valid())

    def test_all_match_types(self):
        """Test all supported match types."""
        match_types = [
            "match",
            "mismatch",
            "one",
            "any",
            "none",
            "greater_than",
            "less_than",
            "contains",
        ]
        for match_type in match_types:
            condition = {
                "type": "instrument",
                "source": "q1",
                "match_type": match_type,
                "values": ["test"],
            }
            serializer = ConditionRuleSerializer(data=condition)
            self.assertTrue(
                serializer.is_valid(), f"Match type {match_type} failed: {serializer.errors}"
            )


class BuilderTests(TestCase):
    """Tests for CollectionRequestBuilder."""

    def test_build_simple_schema(self):
        """Test building a simple schema creates correct objects."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {"measure_id": "q1", "text": "Question 1", "type": "open", "required": True}
                    ],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema)

        self.assertIsNotNone(cr)
        self.assertEqual(cr.collectioninstrument_set.count(), 1)

        instrument = cr.collectioninstrument_set.first()
        self.assertEqual(instrument.measure_id, "q1")
        self.assertEqual(instrument.text, "Question 1")
        self.assertEqual(instrument.group.id, "Section 1")

    def test_build_schema_with_responses(self):
        """Test building schema with suggested responses."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Yes or No?",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                        }
                    ],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema)

        instrument = cr.collectioninstrument_set.first()
        self.assertEqual(instrument.suggested_responses.count(), 2)
        response_values = list(instrument.suggested_responses.values_list("data", flat=True))
        self.assertIn("Yes", response_values)
        self.assertIn("No", response_values)

    def test_build_schema_with_response_sets(self):
        """Test building schema using response_sets."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "response_sets": {"yes-no": ["Yes", "No"]},
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Question",
                            "type": "multiple-choice",
                            "response_set": "yes-no",
                        }
                    ],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema)

        instrument = cr.collectioninstrument_set.first()
        self.assertEqual(instrument.suggested_responses.count(), 2)

    def test_build_schema_with_conditions(self):
        """Test building schema with instrument conditions."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Yes or No?",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                        },
                        {
                            "measure_id": "q2",
                            "text": "Follow up",
                            "type": "open",
                            "conditions": [
                                {
                                    "type": "instrument",
                                    "source": "q1",
                                    "match_type": "match",
                                    "values": ["Yes"],
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema)

        q2 = cr.collectioninstrument_set.get(measure_id="q2")
        self.assertEqual(q2.conditions.count(), 1)

        condition = q2.conditions.first()
        self.assertEqual(condition.data_getter, "instrument:q1")

    def test_build_updates_existing_request(self):
        """Test that building with existing_cr updates it."""
        existing_cr = factories.CollectionRequestFactory.create()
        factories.CollectionInstrumentFactory.create(
            collection_request=existing_cr, measure__id="old-measure"
        )
        self.assertEqual(existing_cr.collectioninstrument_set.count(), 1)

        schema = {
            "version": "1.0",
            "name": "Updated Checklist",
            "sections": [
                {
                    "name": "New Section",
                    "questions": [{"measure_id": "new-q1", "text": "New Question", "type": "open"}],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema, existing_cr=existing_cr)

        self.assertEqual(cr.id, existing_cr.id)
        self.assertEqual(cr.collectioninstrument_set.count(), 1)
        self.assertEqual(cr.collectioninstrument_set.first().measure_id, "new-q1")

    def test_build_preserves_question_order(self):
        """Test that question order is preserved."""
        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {"measure_id": "q1", "text": "First", "type": "open", "order": 10},
                        {"measure_id": "q2", "text": "Second", "type": "open", "order": 20},
                        {"measure_id": "q3", "text": "Third", "type": "open", "order": 30},
                    ],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema)

        instruments = list(cr.collectioninstrument_set.order_by("order"))
        self.assertEqual(instruments[0].measure_id, "q1")
        self.assertEqual(instruments[1].measure_id, "q2")
        self.assertEqual(instruments[2].measure_id, "q3")


class ExporterTests(TestCase):
    """Tests for CollectionRequestExporter."""

    def test_export_simple_schema(self):
        """Test exporting a simple collection request."""
        cr = factories.CollectionRequestFactory.create()
        group = factories.CollectionGroupFactory.create(id="Test Section")
        factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="q1",
            text="Question 1",
            group=group,
            order=10,
        )

        exporter = CollectionRequestExporter()
        schema = exporter.export(cr, name="Test Export")

        self.assertEqual(schema["version"], "1.0")
        self.assertEqual(schema["name"], "Test Export")
        self.assertEqual(len(schema["sections"]), 1)
        self.assertEqual(schema["sections"][0]["name"], "Test Section")
        self.assertEqual(len(schema["sections"][0]["questions"]), 1)
        self.assertEqual(schema["sections"][0]["questions"][0]["measure_id"], "q1")

    def test_export_with_responses(self):
        """Test exporting schema with responses."""
        cr = factories.CollectionRequestFactory.create()
        group = factories.CollectionGroupFactory.create(id="Section 1")
        yes_response = factories.SuggestedResponseFactory.create(data="Yes")
        no_response = factories.SuggestedResponseFactory.create(data="No")

        factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="q1",
            text="Yes or No?",
            group=group,
            suggested_responses=[yes_response, no_response],
        )

        exporter = CollectionRequestExporter()
        schema = exporter.export(cr)

        question = schema["sections"][0]["questions"][0]
        self.assertIn("responses", question)
        self.assertEqual(len(question["responses"]), 2)
        self.assertIn("Yes", question["responses"])
        self.assertIn("No", question["responses"])

    def test_export_creates_response_sets(self):
        """Test that export creates response_sets for repeated patterns."""
        cr = factories.CollectionRequestFactory.create()
        group = factories.CollectionGroupFactory.create(id="Section 1")
        yes_response = factories.SuggestedResponseFactory.create(data="Yes")
        no_response = factories.SuggestedResponseFactory.create(data="No")

        # Create multiple questions with same responses
        for i in range(3):
            factories.CollectionInstrumentFactory.create(
                collection_request=cr,
                measure__id=f"q{i}",
                text=f"Question {i}",
                group=group,
                order=i * 10,
                suggested_responses=[yes_response, no_response],
            )

        exporter = CollectionRequestExporter()
        schema = exporter.export(cr)

        # Should have response_sets with yes-no pattern
        self.assertIn("response_sets", schema)
        self.assertIn("yes-no", schema["response_sets"])
        self.assertEqual(set(schema["response_sets"]["yes-no"]), {"Yes", "No"})

        # Questions should reference response_set instead of inline responses
        for question in schema["sections"][0]["questions"]:
            self.assertIn("response_set", question)
            self.assertEqual(question["response_set"], "yes-no")
            self.assertNotIn("responses", question)

    def test_export_section_has_no_description(self):
        """Test that exported sections don't have description field."""
        cr = factories.CollectionRequestFactory.create()
        group = factories.CollectionGroupFactory.create(id="Test Section")
        factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="q1",
            text="Question",
            group=group,
        )

        exporter = CollectionRequestExporter()
        schema = exporter.export(cr)

        section = schema["sections"][0]
        self.assertNotIn("description", section)

    def test_roundtrip_build_export(self):
        """Test that build -> export produces equivalent schema."""
        original_schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "slug": "section-1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Yes or No?",
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                            "required": True,
                            "order": 10,
                        },
                        {
                            "measure_id": "q2",
                            "text": "Follow up",
                            "type": "open",
                            "required": False,
                            "order": 20,
                            "conditions": [
                                {
                                    "type": "instrument",
                                    "source": "q1",
                                    "match_type": "match",
                                    "values": ["Yes"],
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        # Build and export
        builder = CollectionRequestBuilder()
        cr = builder.build(original_schema)

        exporter = CollectionRequestExporter()
        exported_schema = exporter.export(cr, name="Test Checklist")

        # Verify key properties preserved
        self.assertEqual(len(exported_schema["sections"]), 1)
        self.assertEqual(len(exported_schema["sections"][0]["questions"]), 2)

        q1 = exported_schema["sections"][0]["questions"][0]
        self.assertEqual(q1["measure_id"], "q1")
        self.assertEqual(q1["text"], "Yes or No?")
        self.assertEqual(q1["type"], "multiple-choice")
        self.assertTrue(q1["required"])

        q2 = exported_schema["sections"][0]["questions"][1]
        self.assertEqual(q2["measure_id"], "q2")
        self.assertIn("conditions", q2)
        self.assertEqual(len(q2["conditions"]), 1)
