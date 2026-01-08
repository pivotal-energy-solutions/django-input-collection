"""export_collection_schema.py: Export CollectionRequest to JSON schema"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import logging

from django.core.management.base import BaseCommand, CommandError

from django_input_collection.models import CollectionRequest
from django_input_collection.schema import CollectionRequestExporter

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export a CollectionRequest to JSON schema format"

    def add_arguments(self, parser):
        parser.add_argument(
            "collection_request_id",
            type=int,
            help="CollectionRequest ID to export",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path (default: stdout)",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="Name for the exported schema",
        )

    def handle(self, *args, **options):
        cr_id = options["collection_request_id"]

        try:
            collection_request = CollectionRequest.objects.get(id=cr_id)
        except CollectionRequest.DoesNotExist:
            raise CommandError(f"CollectionRequest {cr_id} not found")

        exporter = CollectionRequestExporter()
        name = options.get("name")

        output_path = options.get("output")
        if output_path:
            exporter.export_to_file(collection_request, output_path, name=name)
            self.stdout.write(self.style.SUCCESS(f"Exported to {output_path}"))
        else:
            json_str = exporter.export_to_json(collection_request, name=name)
            self.stdout.write(json_str)
