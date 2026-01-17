"""exporter.py: Export CollectionRequest to JSON schema"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import json
import logging
from pathlib import Path

from django.utils.text import slugify

from django_input_collection.models import CollectionRequest

from .registry import ConditionResolverRegistry, BoundResponseRegistry

log = logging.getLogger(__name__)


class CollectionRequestExporter:
    """
    Export a CollectionRequest to JSON schema format.

    Supports round-trip: export → modify → import should preserve functionality.

    Usage:
        exporter = CollectionRequestExporter()

        # To dict
        schema = exporter.export(collection_request)

        # To file
        exporter.export_to_file(collection_request, "path/to/schema.json")

        # To JSON string
        json_str = exporter.export_to_json(collection_request)
    """

    # Reverse map from InputType identifier to schema type
    TYPE_MAP = {
        "open": "open",
        "multiple-choice": "multiple-choice",
        "integer": "integer",
        "float": "float",
        "date": "date",
        "cascading-select": "cascading-select",
    }

    # Reverse map from requirement_type to logic
    REQUIREMENT_TO_LOGIC_MAP = {
        "all-pass": "all",
        "one-pass": "any",
        "all-fail": "none",
    }

    def export(self, collection_request: CollectionRequest, name: str = None) -> dict:
        """
        Export a CollectionRequest to JSON schema format.

        Args:
            collection_request: The CollectionRequest to export
            name: Optional name override for the schema

        Returns:
            dict: JSON schema representation
        """
        # Group instruments by section
        sections = self._export_sections(collection_request)

        # Build response sets from common response patterns
        response_sets = self._extract_response_sets(sections)

        # Use program name/slug if available
        derived_name = name
        derived_slug = slugify(name) if name else None
        if not derived_name:
            # Try to find program via related EEPProgram (OneToOneField)
            program = getattr(collection_request, "eepprogram", None)
            if program:
                derived_name = program.name
                derived_slug = program.slug
            else:
                derived_name = "Exported Checklist"
                derived_slug = "exported-checklist"

        schema = {
            "version": "1.0",
            "name": derived_name,
            "slug": derived_slug,
            "description": "",
        }

        # Add response_sets before sections to match documentation order
        if response_sets:
            schema["response_sets"] = response_sets

        schema["sections"] = sections

        return schema

    def export_to_file(
        self, collection_request: CollectionRequest, path: str | Path, **kwargs
    ) -> None:
        """
        Export a CollectionRequest to a JSON file.

        Args:
            collection_request: The CollectionRequest to export
            path: Output file path
            **kwargs: Additional arguments passed to export()
        """
        path = Path(path)
        schema = self.export(collection_request, **kwargs)

        with open(path, "w") as f:
            json.dump(schema, f, indent=2)

        log.info(f"Exported CollectionRequest {collection_request.id} to {path}")

    def export_to_json(self, collection_request: CollectionRequest, **kwargs) -> str:
        """
        Export a CollectionRequest to a JSON string.

        Args:
            collection_request: The CollectionRequest to export
            **kwargs: Additional arguments passed to export()

        Returns:
            str: JSON string representation
        """
        schema = self.export(collection_request, **kwargs)
        return json.dumps(schema, indent=2)

    def _export_sections(self, collection_request: CollectionRequest) -> list:
        """Export instruments grouped by section."""
        sections = {}

        instruments = collection_request.collectioninstrument_set.all().order_by("order")

        for instrument in instruments:
            # Get section from group
            group = instrument.group
            section_name = group.id if group else "Default"
            section_slug = slugify(section_name)

            if section_slug not in sections:
                sections[section_slug] = {
                    "name": section_name,
                    "slug": section_slug,
                    "questions": [],
                }

            question = self._export_instrument(instrument)
            sections[section_slug]["questions"].append(question)

        return list(sections.values())

    def _export_instrument(self, instrument) -> dict:
        """Export a single instrument to question format."""
        question = {
            "measure_id": instrument.measure_id,
            "text": instrument.text,
            "type": self._get_type(instrument),
            "required": instrument.response_policy.required if instrument.response_policy else True,
            "order": instrument.order,
        }

        # Add optional fields if present
        if instrument.description:
            question["description"] = instrument.description
        if instrument.help:
            question["help_text"] = instrument.help

        # Export test_requirement_type if not default
        if instrument.test_requirement_type and instrument.test_requirement_type != "all-pass":
            question["test_requirement_type"] = instrument.test_requirement_type

        # Export responses
        responses = self._export_responses(instrument)
        if responses:
            question["responses"] = responses

        # Export response flags via registry
        flags = BoundResponseRegistry.export(instrument)
        if flags:
            question["response_flags"] = flags

        # Export conditions
        conditions = self._export_conditions(instrument)
        if conditions:
            question["conditions"] = conditions

        return question

    def _get_type(self, instrument) -> str:
        """Get schema type from instrument."""
        if instrument.type:
            return self.TYPE_MAP.get(instrument.type.id, "open")
        return "open"

    def _export_responses(self, instrument) -> list:
        """Export suggested responses for an instrument."""
        responses = []
        for sr in instrument.suggested_responses.all():
            responses.append(sr.data)
        return responses

    def _export_conditions(self, instrument) -> list:
        """
        Export conditions for an instrument.

        Groups conditions by their ConditionGroup to preserve AND/OR logic.
        - If a ConditionGroup has multiple conditions (multiple data_getters),
          they are grouped together with their logic.
        - If all conditions share the same ConditionGroup with non-default logic,
          export as group format.
        - Otherwise, export as simple format for backward compatibility.
        """
        conditions = []
        seen_groups = {}

        # First pass: group conditions by their ConditionGroup
        for condition in instrument.conditions.all():
            group = condition.condition_group
            if not group:
                continue

            group_id = group.id
            if group_id not in seen_groups:
                seen_groups[group_id] = {
                    "group": group,
                    "conditions": [],
                }
            seen_groups[group_id]["conditions"].append(condition)

        # Second pass: export each group
        for group_data in seen_groups.values():
            group = group_data["group"]
            group_conditions = group_data["conditions"]
            logic = self.REQUIREMENT_TO_LOGIC_MAP.get(group.requirement_type, "all")

            # Collect rules for this group, combining values by (type, source, match_type)
            rule_values = {}  # key: (type, source, match_type) -> list of values
            for condition in group_conditions:
                condition_data = self._parse_data_getter(condition.data_getter)
                if not condition_data:
                    continue

                # Get match values from cases and group by rule key
                for case in group.cases.all():
                    parsed_value = self._parse_match_data(case.match_data)
                    # If parsed value is already a list (from stringified tuple), flatten it
                    if isinstance(parsed_value, list):
                        values_to_add = parsed_value
                    else:
                        values_to_add = [parsed_value]

                    rule_key = (condition_data["type"], condition_data["source"], case.match_type)
                    if rule_key not in rule_values:
                        rule_values[rule_key] = []
                    rule_values[rule_key].extend(values_to_add)

            if not rule_values:
                continue

            # Build rules from grouped values
            rules = []
            for (cond_type, source, match_type), values in rule_values.items():
                # Deduplicate values while preserving order
                seen = set()
                unique_values = []
                for v in values:
                    if v not in seen:
                        seen.add(v)
                        unique_values.append(v)
                rules.append(
                    {
                        "type": cond_type,
                        "source": source,
                        "match_type": match_type,
                        "values": unique_values,
                    }
                )

            # Decide on output format
            # Use simple format if: single rule with "all" (AND) logic
            # Use group format if: multiple rules or non-"all" logic
            if len(rules) == 1 and logic == "all":
                # Simple format
                conditions.append(rules[0])
            else:
                conditions.append(
                    {
                        "logic": logic,
                        "rules": rules,
                    }
                )

        return conditions

    def _parse_data_getter(self, data_getter: str) -> dict | None:
        """
        Parse a data_getter string into condition type and source.

        Examples:
            "instrument:measure-id" -> {"type": "instrument", "source": "measure-id"}
            "simulation:floorplan.simulation.x" -> {"type": "simulation", "source": "slug"}
        """
        if ":" not in data_getter:
            return None

        condition_type, path = data_getter.split(":", 1)

        if condition_type == "instrument":
            return {"type": "instrument", "source": path}
        else:
            # Try registry for reverse resolution (path -> slug)
            slug = ConditionResolverRegistry.resolve_export(condition_type, path)
            if slug:
                return {"type": condition_type, "source": slug}
            else:
                # Fall back to using path directly
                log.warning(f"No registry entry found for {condition_type} path: {path}")
                return {"type": condition_type, "source": path}

    def _parse_match_data(self, match_data: str):
        """Parse match_data to appropriate type.

        Handles:
        - Boolean strings ("true", "false")
        - Numeric strings
        - Stringified tuples/lists like "('a', 'b')" -> ['a', 'b']
        """
        if match_data.lower() == "true":
            return True
        if match_data.lower() == "false":
            return False

        # Try to parse as number
        try:
            if "." in match_data:
                return float(match_data)
            return int(match_data)
        except ValueError:
            pass

        # Check for stringified tuple/list like "('a', 'b', 'c')" or "['a', 'b']"
        if (match_data.startswith("(") and match_data.endswith(")")) or (
            match_data.startswith("[") and match_data.endswith("]")
        ):
            try:
                import ast

                parsed = ast.literal_eval(match_data)
                if isinstance(parsed, (list, tuple)):
                    return list(parsed)
            except (ValueError, SyntaxError):
                pass

        return match_data

    def _extract_response_sets(self, sections: list) -> dict:
        """
        Extract common response patterns into reusable response sets.

        Detects patterns that appear 2+ times and creates named sets.
        Updates questions in-place to reference sets instead of inline arrays.
        """
        from collections import Counter

        # Collect all response patterns
        response_patterns = Counter()
        for section in sections:
            for question in section.get("questions", []):
                responses = question.get("responses", [])
                if responses:
                    # Use tuple for hashability
                    pattern = tuple(responses)
                    response_patterns[pattern] += 1

        # Create named sets for patterns appearing 2+ times
        response_sets = {}
        pattern_to_name = {}
        used_names = {}  # name -> pattern, to detect collisions

        for pattern, count in response_patterns.items():
            if count >= 2:
                name = self._generate_response_set_name(pattern)

                # Handle name collisions
                if name in used_names and used_names[name] != pattern:
                    # Add suffix to make unique
                    suffix = 2
                    base_name = name
                    while name in used_names:
                        name = f"{base_name}-{suffix}"
                        suffix += 1

                response_sets[name] = list(pattern)
                pattern_to_name[pattern] = name
                used_names[name] = pattern

        # Update questions to reference sets instead of inline arrays
        if pattern_to_name:
            for section in sections:
                for question in section.get("questions", []):
                    responses = question.get("responses", [])
                    if responses:
                        pattern = tuple(responses)
                        if pattern in pattern_to_name:
                            question["response_set"] = pattern_to_name[pattern]
                            del question["responses"]

        return response_sets

    def _generate_response_set_name(self, pattern: tuple) -> str:
        """Generate a meaningful name for a response set pattern."""
        pattern_lower = [r.lower() for r in pattern]

        # Check for common patterns
        if set(pattern_lower) == {"yes", "no"}:
            return "yes-no"
        if set(pattern_lower) == {"yes", "no", "n/a"}:
            return "yes-no-na"
        if set(pattern_lower) == {"pass", "fail"}:
            return "pass-fail"
        if set(pattern_lower) == {"pass", "fail", "n/a"}:
            return "pass-fail-na"

        # Generate slug from first few responses
        slug_parts = []
        for resp in pattern[:3]:
            # Take first word, lowercase, remove special chars
            word = resp.split()[0].lower() if resp else ""
            word = "".join(c for c in word if c.isalnum())
            if word:
                slug_parts.append(word)

        if len(pattern) > 3:
            slug_parts.append(f"plus{len(pattern) - 3}")

        return "-".join(slug_parts) if slug_parts else f"set-{hash(pattern) % 10000}"
