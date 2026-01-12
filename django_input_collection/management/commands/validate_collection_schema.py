"""validate_collection_schema.py: Validate a collection JSON schema"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from django_input_collection.schema import CollectionSchemaSerializer

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Validate a collection JSON schema without importing"

    def add_arguments(self, parser):
        parser.add_argument(
            "input_file",
            type=str,
            help="Path to JSON schema file",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show detailed validation information",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input_file"])
        verbose = options.get("verbose", False)

        if not input_path.exists():
            raise CommandError(f"File not found: {input_path}")

        # Load JSON
        with open(input_path) as f:
            try:
                schema = json.load(f)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON at line {e.lineno}: {e.msg}")

        # Validate with serializer
        serializer = CollectionSchemaSerializer(data=schema)
        is_valid = serializer.is_valid()

        if is_valid:
            self.stdout.write(self.style.SUCCESS("Schema is valid"))
            self._print_summary(serializer.validated_data, verbose)
        else:
            self.stderr.write(self.style.ERROR("Schema validation failed:"))
            self._print_errors(serializer.errors)
            raise CommandError("Validation failed")

    def _print_summary(self, schema: dict, verbose: bool):
        """Print schema summary."""
        self.stdout.write("")
        self.stdout.write(f"  Name: {schema.get('name', 'Unnamed')}")
        self.stdout.write(f"  Version: {schema.get('version', '1.0')}")

        sections = schema.get("sections", [])
        total_questions = sum(len(s.get("questions", [])) for s in sections)

        self.stdout.write(f"  Sections: {len(sections)}")
        self.stdout.write(f"  Questions: {total_questions}")

        # Count conditions by type
        instrument_conditions = 0
        other_conditions = 0
        for section in sections:
            for question in section.get("questions", []):
                for cond in question.get("conditions", []):
                    if cond.get("type") == "instrument":
                        instrument_conditions += 1
                    elif cond.get("type"):
                        other_conditions += 1
                    # Handle group format
                    for rule in cond.get("rules", []):
                        if rule.get("type") == "instrument":
                            instrument_conditions += 1
                        elif rule.get("type"):
                            other_conditions += 1

        if instrument_conditions or other_conditions:
            self.stdout.write("  Conditions:")
            if instrument_conditions:
                self.stdout.write(f"    - Instrument: {instrument_conditions}")
            if other_conditions:
                self.stdout.write(f"    - Other: {other_conditions}")

        # Response sets
        response_sets = schema.get("response_sets", {})
        if response_sets:
            self.stdout.write(f"  Response Sets: {len(response_sets)}")

        if verbose:
            self.stdout.write("")
            self.stdout.write("  Sections:")
            for section in sections:
                questions = section.get("questions", [])
                self.stdout.write(f"    - {section['name']}: {len(questions)} questions")
                if verbose:
                    for q in questions:
                        q_type = q.get("type", "open")
                        required = "required" if q.get("required", True) else "optional"
                        conditions = len(q.get("conditions", []))
                        cond_str = f" ({conditions} conditions)" if conditions else ""
                        self.stdout.write(
                            f"      - {q['measure_id']} [{q_type}, {required}]{cond_str}"
                        )

        self.stdout.write("")

    def _print_errors(self, errors: dict, prefix: str = ""):
        """Recursively print validation errors."""
        for field, field_errors in errors.items():
            if isinstance(field_errors, dict):
                self._print_errors(field_errors, prefix=f"{prefix}{field}.")
            elif isinstance(field_errors, list):
                for error in field_errors:
                    if isinstance(error, dict):
                        self._print_errors(error, prefix=f"{prefix}{field}.")
                    else:
                        self.stderr.write(f"  {prefix}{field}: {error}")
            else:
                self.stderr.write(f"  {prefix}{field}: {field_errors}")
