"""serializers.py: Collection request JSON schema validation serializers"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import logging
from typing import Callable

from rest_framework import serializers

log = logging.getLogger(__name__)


class ConditionValidatorRegistry:
    """
    Registry for condition validators that validate schema condition sources.

    Allows applications to register validators for custom condition types.

    Usage:
        @register_condition_validator('simulation')
        def validate_simulation_condition(source: str, values: list) -> tuple[bool, str | None]:
            '''Validate a simulation condition source and values.

            Returns:
                Tuple of (is_valid, error_message)
            '''
            registry_entry = SimulationConditionRegistry.get_by_slug(source)
            if not registry_entry:
                return False, f"Unknown simulation condition slug: '{source}'"

            for value in values:
                is_valid, error = registry_entry.validate_value(value)
                if not is_valid:
                    return False, error

            return True, None
    """

    _validators: dict[str, Callable[[str, list], tuple[bool, str | None]]] = {}

    @classmethod
    def register(
        cls,
        condition_type: str,
        validator: Callable[[str, list], tuple[bool, str | None]],
    ):
        """
        Register a validator for a condition type.

        Args:
            condition_type: The condition type (e.g., 'simulation')
            validator: Callable(source, values) -> (is_valid, error_message)
        """
        cls._validators[condition_type] = validator

    @classmethod
    def validate(cls, condition_type: str, source: str, values: list) -> tuple[bool, str | None]:
        """
        Validate a condition source and values.

        Args:
            condition_type: The condition type (e.g., 'instrument', 'simulation')
            source: The source identifier
            values: The match values

        Returns:
            Tuple of (is_valid, error_message or None)
        """
        # Built-in instrument type - no validation (validated in ChecklistSchemaSerializer)
        if condition_type == "instrument":
            return True, None

        # Check registered validators
        validator = cls._validators.get(condition_type)
        if validator:
            return validator(source, values)

        # Unknown condition type - allow by default (validator can be added later)
        log.warning(f"No validator registered for condition type: {condition_type}")
        return True, None


def register_condition_validator(condition_type: str):
    """
    Decorator to register a condition validator.

    Usage:
        @register_condition_validator('simulation')
        def validate_simulation(source, values):
            ...
    """

    def decorator(func):
        ConditionValidatorRegistry.register(condition_type, func)
        return func

    return decorator


class TypeConstraintsSerializer(serializers.Serializer):
    """
    Type-specific constraints for question validation.

    Used differently based on question type:
    - integer/float: min, max
    - open: max_length
    - date: min_date, max_date (ISO format strings)
    """

    # Numeric constraints (integer, float)
    min = serializers.FloatField(required=False, allow_null=True)
    max = serializers.FloatField(required=False, allow_null=True)

    # Text constraints (open)
    max_length = serializers.IntegerField(required=False, min_value=1, allow_null=True)

    # Date constraints (ISO format: YYYY-MM-DD)
    min_date = serializers.DateField(required=False, allow_null=True)
    max_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        """Validate constraint combinations"""
        min_val = data.get("min")
        max_val = data.get("max")
        if min_val is not None and max_val is not None and min_val > max_val:
            raise serializers.ValidationError({"min": "min cannot be greater than max"})

        min_date = data.get("min_date")
        max_date = data.get("max_date")
        if min_date is not None and max_date is not None and min_date > max_date:
            raise serializers.ValidationError({"min_date": "min_date cannot be after max_date"})

        return data


class ResponseFlagsSerializer(serializers.Serializer):
    """Flags for a specific response choice"""

    comment_required = serializers.BooleanField(required=False, default=False)
    photo_required = serializers.BooleanField(required=False, default=False)
    document_required = serializers.BooleanField(required=False, default=False)
    is_considered_failure = serializers.BooleanField(required=False, default=False)


class ConditionRuleSerializer(serializers.Serializer):
    """
    A single condition rule that controls when a question is shown.

    Conditions reference either:
    - Another question's answer (type="instrument", source=measure_id)
    - A custom condition type (type="simulation", source=registry_slug, etc.)
    """

    # Default supported types - can be extended via registry
    DEFAULT_CONDITION_TYPES = ["instrument", "simulation"]

    type = serializers.CharField(
        help_text="Condition type: 'instrument' for question references, or custom type"
    )
    source = serializers.CharField(
        help_text="measure_id for instrument conditions, or type-specific identifier"
    )
    match_type = serializers.ChoiceField(
        choices=[
            "match",
            "mismatch",
            "one",
            "zero",
            "any",
            "none",
            "greater_than",
            "less_than",
            "contains",
        ],
        default="match",
        help_text="How to match values: match (exact), one (any of list), zero (not any of list), etc.",
    )
    values = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        help_text="Values to match against. For boolean, use [true] or [false].",
    )

    def validate(self, data):
        """Validate condition source using registry"""
        condition_type = data.get("type")
        source = data.get("source")
        values = data.get("values", [])

        # Validate via registry (instrument validated later in parent)
        if condition_type != "instrument":
            is_valid, error = ConditionValidatorRegistry.validate(condition_type, source, values)
            if not is_valid:
                raise serializers.ValidationError({"source": error})

        return data


class ConditionGroupSerializer(serializers.Serializer):
    """
    A group of condition rules with AND/OR logic.

    Examples:
        Show if Q1=Yes AND Q2=No:
        {
            "logic": "all",
            "rules": [
                {"type": "instrument", "source": "q1", "match_type": "match", "values": ["Yes"]},
                {"type": "instrument", "source": "q2", "match_type": "match", "values": ["No"]}
            ]
        }

        Show if Q1=Yes OR Q2=Yes:
        {
            "logic": "any",
            "rules": [
                {"type": "instrument", "source": "q1", "match_type": "match", "values": ["Yes"]},
                {"type": "instrument", "source": "q2", "match_type": "match", "values": ["Yes"]}
            ]
        }
    """

    LOGIC_TYPES = ["all", "any", "none"]

    logic = serializers.ChoiceField(
        choices=LOGIC_TYPES,
        default="all",
        help_text="all=AND (all rules must pass), any=OR (one rule must pass), none=NAND (all must fail)",
    )
    rules = ConditionRuleSerializer(many=True, help_text="List of condition rules")

    def validate_rules(self, rules):
        """Ensure at least one rule in the group"""
        if not rules:
            raise serializers.ValidationError("Condition group must have at least one rule")
        return rules


class QuestionConditionSerializer(serializers.Serializer):
    """
    Condition that controls when a question is shown.

    Supports two formats for backward compatibility:

    Simple format (single rule, implicit AND):
        {"type": "instrument", "source": "q1", "match_type": "match", "values": ["Yes"]}

    Group format (multiple rules with logic):
        {"logic": "any", "rules": [...]}

    The serializer normalizes both formats to the group format internally.
    """

    # Fields for simple format (single rule)
    type = serializers.CharField(required=False)
    source = serializers.CharField(required=False)
    match_type = serializers.ChoiceField(
        choices=[
            "match",
            "mismatch",
            "one",
            "zero",
            "any",
            "none",
            "greater_than",
            "less_than",
            "contains",
        ],
        default="match",
        required=False,
    )
    values = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
    )

    # Fields for group format
    logic = serializers.ChoiceField(
        choices=ConditionGroupSerializer.LOGIC_TYPES,
        required=False,
    )
    rules = ConditionRuleSerializer(many=True, required=False)

    def validate(self, data):
        """Validate and normalize condition format"""
        has_simple_fields = data.get("type") is not None
        has_group_fields = data.get("rules") is not None

        if has_simple_fields and has_group_fields:
            raise serializers.ValidationError(
                "Cannot mix simple format (type/source) with group format (logic/rules)"
            )

        if not has_simple_fields and not has_group_fields:
            raise serializers.ValidationError(
                "Must provide either simple format (type, source) or group format (logic, rules)"
            )

        if has_simple_fields:
            # Validate simple format
            if not data.get("source"):
                raise serializers.ValidationError(
                    {"source": "Required for simple condition format"}
                )

            # Validate via registry (instrument validated later in parent)
            condition_type = data["type"]
            if condition_type != "instrument":
                source = data["source"]
                values = data.get("values", [])
                is_valid, error = ConditionValidatorRegistry.validate(
                    condition_type, source, values
                )
                if not is_valid:
                    raise serializers.ValidationError({"source": error})

        if has_group_fields:
            # Validate group format has at least one rule
            if not data.get("rules"):
                raise serializers.ValidationError({"rules": "Required for group condition format"})

        return data

    def to_internal_value(self, data):
        """Convert input data, normalizing to internal format"""
        result = super().to_internal_value(data)

        # Normalize simple format to include a marker for processing
        if result.get("type") is not None:
            result["_format"] = "simple"
        else:
            result["_format"] = "group"
            # Default logic to "all" if not specified
            if "logic" not in result:
                result["logic"] = "all"

        return result


class QuestionSerializer(serializers.Serializer):
    """
    A single question/instrument in the checklist.
    """

    QUESTION_TYPES = [
        "open",
        "multiple-choice",
        "integer",
        "float",
        "date",
        "cascading-select",
    ]

    measure_id = serializers.SlugField(
        help_text="Unique identifier for this question within the checklist"
    )
    text = serializers.CharField(help_text="The question text displayed to users")
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Additional description shown below the question",
    )
    help_text = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Help text shown on hover or in help modal",
    )
    type = serializers.ChoiceField(
        choices=QUESTION_TYPES,
        default="open",
        help_text="Question type determines input widget",
    )
    responses = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="For multiple-choice: list of response options",
    )
    response_set = serializers.CharField(
        required=False,
        help_text="Reference to a named response set defined in response_sets",
    )
    required = serializers.BooleanField(
        default=True,
        help_text="Whether this question must be answered",
    )
    test_requirement_type = serializers.ChoiceField(
        choices=["all-pass", "one-pass", "all-fail"],
        default="all-pass",
        required=False,
        help_text="How multiple conditions are evaluated",
    )
    constraints = TypeConstraintsSerializer(
        required=False,
        help_text="Type-specific validation constraints (min/max for numbers, max_length for text, etc.)",
    )
    response_flags = serializers.DictField(
        child=ResponseFlagsSerializer(),
        required=False,
        help_text="Per-response flags like comment_required. Keys are response values.",
    )
    conditions = QuestionConditionSerializer(
        many=True,
        required=False,
        help_text="Conditions that must be met for this question to be shown",
    )
    order = serializers.IntegerField(
        required=False,
        help_text="Explicit ordering (auto-assigned if not provided)",
    )

    def validate(self, data):
        """Validate question configuration"""
        question_type = data.get("type", "open")
        responses = data.get("responses", [])
        response_set = data.get("response_set")
        constraints = data.get("constraints", {})

        # Multiple-choice requires responses or response_set
        if question_type == "multiple-choice" and not responses and not response_set:
            raise serializers.ValidationError(
                {"responses": "Multiple-choice questions require responses or response_set"}
            )

        # Validate response_flags keys match responses (if inline responses provided)
        response_flags = data.get("response_flags", {})
        if response_flags and responses:
            invalid_keys = set(response_flags.keys()) - set(responses)
            if invalid_keys:
                raise serializers.ValidationError(
                    {
                        "response_flags": (
                            f"Response flags reference unknown responses: {invalid_keys}. "
                            f"Valid responses: {responses}"
                        )
                    }
                )

        # Validate constraints match question type
        if constraints:
            self._validate_constraints_for_type(question_type, constraints)

        return data

    def _validate_constraints_for_type(self, question_type: str, constraints: dict):
        """Validate that constraints are appropriate for the question type"""
        numeric_constraints = {"min", "max"}
        text_constraints = {"max_length"}
        date_constraints = {"min_date", "max_date"}

        provided = set(k for k, v in constraints.items() if v is not None)

        if question_type in ("integer", "float"):
            invalid = provided - numeric_constraints
            if invalid:
                raise serializers.ValidationError(
                    {
                        "constraints": f"Invalid constraints for {question_type} type: {invalid}. Use min/max."
                    }
                )
        elif question_type == "open":
            invalid = provided - text_constraints
            if invalid:
                raise serializers.ValidationError(
                    {
                        "constraints": f"Invalid constraints for open type: {invalid}. Use max_length."
                    }
                )
        elif question_type == "date":
            invalid = provided - date_constraints
            if invalid:
                raise serializers.ValidationError(
                    {
                        "constraints": f"Invalid constraints for date type: {invalid}. Use min_date/max_date."
                    }
                )
        elif question_type in ("multiple-choice", "cascading-select"):
            if provided:
                raise serializers.ValidationError(
                    {"constraints": f"{question_type} type does not support constraints"}
                )


class SectionSerializer(serializers.Serializer):
    """
    A section/group of questions in the checklist.
    """

    name = serializers.CharField(help_text="Section name displayed as header")
    slug = serializers.SlugField(
        required=False,
        help_text="URL-safe identifier (auto-generated from name if not provided)",
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional section description",
    )
    questions = QuestionSerializer(many=True, help_text="Questions in this section")
    order = serializers.IntegerField(
        required=False,
        help_text="Section ordering (auto-assigned if not provided)",
    )

    def validate_questions(self, questions):
        """Ensure at least one question per section"""
        if not questions:
            raise serializers.ValidationError("Each section must have at least one question")
        return questions


class CollectionSchemaSerializer(serializers.Serializer):
    """
    Top-level collection schema serializer.

    Validates the complete JSON schema for a collection request definition.
    Used to validate checklist_schema JSONField on templates before saving.
    """

    version = serializers.CharField(
        default="1.0",
        help_text="Schema version for future compatibility",
    )
    name = serializers.CharField(help_text="Human-readable checklist name")
    slug = serializers.SlugField(
        required=False,
        help_text="URL-safe identifier (auto-generated from name if not provided)",
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Checklist description",
    )

    # Reusable response sets
    response_sets = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=False,
        help_text="Named response sets that can be referenced by questions",
    )

    sections = SectionSerializer(many=True, help_text="Sections containing questions")

    def validate_sections(self, sections):
        """Ensure at least one section"""
        if not sections:
            raise serializers.ValidationError("Checklist must have at least one section")
        return sections

    def validate(self, data):
        """Cross-field validation"""
        sections = data.get("sections", [])
        response_sets = data.get("response_sets", {})

        # Collect all measure_ids to check for duplicates and validate conditions
        all_measure_ids = set()
        duplicate_ids = set()

        for section in sections:
            for question in section.get("questions", []):
                measure_id = question.get("measure_id")
                if measure_id in all_measure_ids:
                    duplicate_ids.add(measure_id)
                all_measure_ids.add(measure_id)

        if duplicate_ids:
            raise serializers.ValidationError(
                {"sections": f"Duplicate measure_ids found: {duplicate_ids}"}
            )

        # Validate instrument condition sources reference valid measure_ids
        # Validate response_set references
        for section in sections:
            for question in section.get("questions", []):
                # Validate response_set reference
                response_set_name = question.get("response_set")
                if response_set_name and response_set_name not in response_sets:
                    raise serializers.ValidationError(
                        {
                            "sections": (
                                f"Question '{question.get('measure_id')}' references "
                                f"unknown response_set: '{response_set_name}'"
                            )
                        }
                    )

                # Validate instrument conditions
                for condition in question.get("conditions", []):
                    if condition.get("type") == "instrument":
                        source = condition.get("source")
                        if source not in all_measure_ids:
                            raise serializers.ValidationError(
                                {
                                    "sections": (
                                        f"Question '{question.get('measure_id')}' has condition "
                                        f"referencing unknown measure_id: '{source}'"
                                    )
                                }
                            )
                    # Handle group format conditions
                    elif condition.get("rules"):
                        for rule in condition.get("rules", []):
                            if rule.get("type") == "instrument":
                                source = rule.get("source")
                                if source not in all_measure_ids:
                                    raise serializers.ValidationError(
                                        {
                                            "sections": (
                                                f"Question '{question.get('measure_id')}' has condition "
                                                f"referencing unknown measure_id: '{source}'"
                                            )
                                        }
                                    )

        return data


# Alias for backward compatibility
ChecklistSchemaSerializer = CollectionSchemaSerializer
