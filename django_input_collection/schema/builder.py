"""builder.py: Build CollectionRequest from JSON schema"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import json
import logging
from pathlib import Path

from django.utils.text import slugify

from django_input_collection.models import (
    CollectionRequest,
    CollectionInstrument,
    CollectionInstrumentType,
    Measure,
    CollectionGroup,
    ResponsePolicy,
    SuggestedResponse,
)
from django_input_collection.models.conditions import (
    Condition,
    ConditionGroup,
    Case,
)

from .registry import ConditionResolverRegistry, BoundResponseRegistry

log = logging.getLogger(__name__)


class CollectionRequestBuilder:
    """
    Build a CollectionRequest from a validated JSON schema.

    Usage:
        builder = CollectionRequestBuilder()

        # From dict
        collection_request = builder.build(schema_dict)

        # From file
        collection_request = builder.build_from_file("path/to/schema.json")

        # Update existing
        collection_request = builder.build(schema_dict, existing_cr)
    """

    # Maps schema type to InputType identifier
    TYPE_MAP = {
        "open": "open",
        "multiple-choice": "multiple-choice",
        "integer": "integer",
        "float": "float",
        "date": "date",
        "cascading-select": "cascading-select",
    }

    # Match type mappings
    MATCH_TYPE_MAP = {
        "match": "match",
        "mismatch": "mismatch",
        "one": "one",
        "zero": "zero",
        "any": "any",
        "none": "none",
        "greater_than": "greater_than",
        "less_than": "less_than",
        "contains": "contains",
    }

    # Logic type to requirement_type mapping
    LOGIC_TO_REQUIREMENT_MAP = {
        "all": "all-pass",
        "any": "one-pass",
        "none": "all-fail",
    }

    def __init__(self):
        self.errors = []
        self.warnings = []
        self._measure_cache = {}
        self._instrument_cache = {}
        self._response_sets = {}

    def build(self, schema: dict, existing_cr: CollectionRequest = None) -> CollectionRequest:
        """
        Build a CollectionRequest from a validated schema dict.

        Args:
            schema: Validated schema dictionary
            existing_cr: Optional existing CollectionRequest to update

        Returns:
            CollectionRequest instance
        """
        self.errors = []
        self.warnings = []
        self._measure_cache = {}
        self._instrument_cache = {}
        self._response_sets = schema.get("response_sets", {})

        # Create or get CollectionRequest
        if existing_cr:
            collection_request = existing_cr
            # Clear existing instruments if updating
            collection_request.collectioninstrument_set.all().delete()
        else:
            collection_request = CollectionRequest.objects.create()

        # Build sections and instruments
        order = 0
        for section_data in schema.get("sections", []):
            # Use section name as group ID (CollectionGroup only has id field)
            section_name = section_data["name"]
            section_group = self._get_or_create_group(section_name)

            for question_data in section_data.get("questions", []):
                order += 1
                instrument = self._build_instrument(
                    collection_request=collection_request,
                    question=question_data,
                    section_group=section_group,
                    order=question_data.get("order", order),
                )
                self._instrument_cache[question_data["measure_id"]] = instrument

        # Build conditions (second pass - all instruments must exist first)
        for section_data in schema.get("sections", []):
            for question_data in section_data.get("questions", []):
                conditions = question_data.get("conditions", [])
                if conditions:
                    instrument = self._instrument_cache[question_data["measure_id"]]
                    self._build_conditions(instrument, conditions)

        return collection_request

    def build_from_file(self, path: str | Path, serializer_class=None) -> CollectionRequest:
        """
        Build a CollectionRequest from a JSON file.

        Args:
            path: Path to JSON schema file
            serializer_class: Optional serializer class for validation.
                              If not provided, uses CollectionSchemaSerializer from this module.

        Returns:
            CollectionRequest instance
        """
        path = Path(path)
        with open(path) as f:
            schema = json.load(f)

        # Validate with serializer if provided
        if serializer_class is None:
            from .serializers import CollectionSchemaSerializer

            serializer_class = CollectionSchemaSerializer

        serializer = serializer_class(data=schema)
        serializer.is_valid(raise_exception=True)

        return self.build(serializer.validated_data)

    def _get_or_create_measure(self, measure_id: str) -> Measure:
        """Get or create a Measure by ID."""
        if measure_id not in self._measure_cache:
            measure, _ = Measure.objects.get_or_create(id=measure_id)
            self._measure_cache[measure_id] = measure
        return self._measure_cache[measure_id]

    def _get_or_create_group(self, name: str) -> CollectionGroup:
        """Get or create a CollectionGroup."""
        # CollectionGroup only has id field, use name as id for round-trip stability
        group, _ = CollectionGroup.objects.get_or_create(id=name)
        return group

    def _get_or_create_type(self, type_id: str) -> CollectionInstrumentType:
        """Get or create a CollectionInstrumentType."""
        mapped_type = self.TYPE_MAP.get(type_id, "open")
        input_type, _ = CollectionInstrumentType.objects.get_or_create(id=mapped_type)
        return input_type

    def _get_or_create_response_policy(self, required: bool, has_responses: bool) -> ResponsePolicy:
        """Get or create a ResponsePolicy."""
        policy, _ = ResponsePolicy.objects.get_or_create(
            required=required,
            restrict=has_responses,  # Restrict to suggested responses if we have them
            multiple=False,
        )
        return policy

    def _build_instrument(
        self,
        collection_request: CollectionRequest,
        question: dict,
        section_group: CollectionGroup,
        order: int,
    ) -> CollectionInstrument:
        """Build a single CollectionInstrument from question data."""
        measure = self._get_or_create_measure(question["measure_id"])
        input_type = self._get_or_create_type(question.get("type", "open"))

        # Get responses - either inline or from response_set reference
        responses = question.get("responses", [])
        if not responses and "response_set" in question:
            response_set_name = question["response_set"]
            responses = self._response_sets.get(response_set_name, [])

        response_policy = self._get_or_create_response_policy(
            required=question.get("required", True),
            has_responses=bool(responses),
        )

        # Create checklist group
        checklist_group = self._get_or_create_group("checklist")

        instrument = CollectionInstrument.objects.create(
            collection_request=collection_request,
            measure=measure,
            type=input_type,
            segment=checklist_group,
            group=section_group,
            response_policy=response_policy,
            text=question["text"],
            description=question.get("description", ""),
            help=question.get("help_text", ""),
            order=order,
            test_requirement_type=question.get("test_requirement_type", "all-pass"),
        )

        # Add suggested responses with optional flags
        response_flags = question.get("response_flags", {})
        for response_value in responses:
            suggested_response = self._get_or_create_suggested_response(response_value)
            flags = response_flags.get(response_value, {})

            # Use registry to create bound response with flags
            BoundResponseRegistry.create(instrument, suggested_response, flags)

        return instrument

    def _get_or_create_suggested_response(self, data: str) -> SuggestedResponse:
        """Get or create a SuggestedResponse."""
        response, _ = SuggestedResponse.objects.get_or_create(data=data)
        return response

    def _build_conditions(self, instrument: CollectionInstrument, conditions: list):
        """
        Build conditions for an instrument.

        Supports both simple and group condition formats:
        - Simple: {"type": "instrument", "source": "q1", "values": ["Yes"]}
        - Group: {"logic": "any", "rules": [...]}

        Format is detected by presence of "rules" key (group) or "type" key (simple).
        """
        for condition_data in conditions:
            # Detect format: group format has "rules", simple format has "type"
            is_group_format = "rules" in condition_data

            if is_group_format:
                # Group format: multiple rules with explicit logic
                self._build_condition_group(instrument, condition_data)
            else:
                # Simple format: single rule, implicit all-pass
                self._build_simple_condition(instrument, condition_data)

    def _build_simple_condition(self, instrument: CollectionInstrument, condition_data: dict):
        """Build a single condition from simple format."""
        condition_type = condition_data["type"]
        source = condition_data["source"]
        match_type = condition_data.get("match_type", "match")
        values = condition_data.get("values", [])

        data_getter = self._resolve_data_getter(condition_type, source, values)
        if not data_getter:
            return

        # Create ONE condition group with ALL values as cases
        condition_group = self._create_condition_group_for_rule(
            data_getter=data_getter,
            match_type=match_type,
            values=values,
            logic="all",
        )

        Condition.objects.get_or_create(
            instrument=instrument,
            condition_group=condition_group,
            data_getter=data_getter,
        )

    def _build_condition_group(self, instrument: CollectionInstrument, condition_data: dict):
        """
        Build conditions from group format with AND/OR logic.

        For group format, we create ONE ConditionGroup with appropriate requirement_type,
        but separate Condition objects for each rule (each with its own data_getter).
        """
        logic = condition_data.get("logic", "all")
        rules = condition_data.get("rules", [])

        if not rules:
            return

        # For multiple rules with same logic, create a shared ConditionGroup
        requirement_type = self.LOGIC_TO_REQUIREMENT_MAP.get(logic, "all-pass")

        # Build nickname from rules
        rule_summaries = []
        for rule in rules:
            source = rule.get("source", "?")
            values = rule.get("values", [])
            rule_summaries.append(f"{source}={values[0] if values else '?'}")
        nickname = f"{logic}({', '.join(rule_summaries)})"[:100]

        # Create the condition group
        condition_group = ConditionGroup.objects.create(
            nickname=nickname,
            requirement_type=requirement_type,
        )

        # Add cases for each rule
        for rule in rules:
            condition_type = rule["type"]
            source = rule["source"]
            match_type = rule.get("match_type", "match")
            values = rule.get("values", [])

            data_getter = self._resolve_data_getter(condition_type, source, values)
            if not data_getter:
                continue

            # Create case for this rule's values
            for value in values:
                case, _ = Case.objects.get_or_create(
                    match_type=self.MATCH_TYPE_MAP.get(match_type, "match"),
                    match_data=str(value) if not isinstance(value, str) else value,
                )
                condition_group.cases.add(case)

            # Create Condition linking instrument to group via this data_getter
            Condition.objects.get_or_create(
                instrument=instrument,
                condition_group=condition_group,
                data_getter=data_getter,
            )

    def _resolve_data_getter(
        self, condition_type: str, source: str, values: list | None = None
    ) -> str | None:
        """
        Resolve condition type and source to a data_getter string.

        Uses ConditionResolverRegistry for custom condition types.
        """
        return ConditionResolverRegistry.resolve_import(condition_type, source, values)

    def _create_condition_group_for_rule(
        self, data_getter: str, match_type: str, values: list, logic: str = "all"
    ) -> ConditionGroup:
        """Create a ConditionGroup for a single rule."""
        # Create readable nickname
        source = data_getter.split(":")[-1].split(".")[-1]
        value_str = ",".join(str(v) for v in values)
        nickname = f"{source}={value_str}"[:100]

        requirement_type = self.LOGIC_TO_REQUIREMENT_MAP.get(logic, "all-pass")

        condition_group, created = ConditionGroup.objects.get_or_create(
            nickname=nickname,
            defaults={"requirement_type": requirement_type},
        )

        if created:
            # Create case for each value
            for value in values:
                case, _ = Case.objects.get_or_create(
                    match_type=self.MATCH_TYPE_MAP.get(match_type, "match"),
                    match_data=str(value) if not isinstance(value, str) else value,
                )
                condition_group.cases.add(case)

        return condition_group
