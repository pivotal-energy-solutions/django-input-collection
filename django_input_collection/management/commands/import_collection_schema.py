"""import_collection_schema.py: Import CollectionRequest from JSON schema"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from django_input_collection.models import CollectionRequest
from django_input_collection.schema import CollectionRequestBuilder, CollectionSchemaSerializer

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import a CollectionRequest from JSON schema file"

    def add_arguments(self, parser):
        parser.add_argument(
            "input_file",
            type=str,
            help="Path to JSON schema file",
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Only validate the schema, don't create CollectionRequest",
        )
        parser.add_argument(
            "--update-id",
            type=int,
            help="Update existing CollectionRequest instead of creating new",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input_file"])

        if not input_path.exists():
            raise CommandError(f"File not found: {input_path}")

        # Load and validate
        with open(input_path) as f:
            try:
                schema = json.load(f)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON: {e}")

        # Validate with serializer
        serializer = CollectionSchemaSerializer(data=schema)
        if not serializer.is_valid():
            self.stderr.write(self.style.ERROR("Schema validation failed:"))
            for field, errors in serializer.errors.items():
                for error in errors:
                    self.stderr.write(f"  {field}: {error}")
            raise CommandError("Schema validation failed")

        self.stdout.write(self.style.SUCCESS("Schema validated successfully"))

        # Show summary
        validated = serializer.validated_data
        self._print_summary(validated)

        if options.get("validate_only"):
            return

        # Get existing CR if updating
        existing_cr = None
        update_id = options.get("update_id")
        if update_id:
            try:
                existing_cr = CollectionRequest.objects.get(id=update_id)
                self.stdout.write(f"Will update CollectionRequest {update_id}")
            except CollectionRequest.DoesNotExist:
                raise CommandError(f"CollectionRequest {update_id} not found")

        # Build CollectionRequest
        builder = CollectionRequestBuilder()
        collection_request = builder.build(validated, existing_cr=existing_cr)

        if existing_cr:
            self.stdout.write(
                self.style.SUCCESS(f"Updated CollectionRequest {collection_request.id}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Created CollectionRequest {collection_request.id}")
            )

        # Report any warnings/errors
        if builder.warnings:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for warning in builder.warnings:
                self.stdout.write(f"  - {warning}")

        if builder.errors:
            self.stderr.write(self.style.ERROR("Errors:"))
            for error in builder.errors:
                self.stderr.write(f"  - {error}")

    def _print_summary(self, schema: dict):
        """Print schema summary."""
        self.stdout.write("")
        self.stdout.write(f"  Name: {schema.get('name', 'Unnamed')}")
        self.stdout.write(f"  Version: {schema.get('version', '1.0')}")

        sections = schema.get("sections", [])
        total_questions = sum(len(s.get("questions", [])) for s in sections)

        self.stdout.write(f"  Sections: {len(sections)}")
        self.stdout.write(f"  Questions: {total_questions}")

        # Count conditions
        conditions_count = 0
        for section in sections:
            for question in section.get("questions", []):
                conditions_count += len(question.get("conditions", []))

        if conditions_count:
            self.stdout.write(f"  Conditions: {conditions_count}")

        self.stdout.write("")
