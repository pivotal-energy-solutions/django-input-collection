"""mixins.py: DRF ViewSet mixins for checklist schema and collection

These mixins provide reusable API endpoints for:
- ChecklistSchemaMixin: Admin-level schema management (export/import)
- ChecklistConsumerMixin: Consumer-level checklist interaction (view/submit answers)
"""

__author__ = "Steven Klass"
__date__ = "01/08/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import logging
from typing import Any, Callable, Optional

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .serializers import ChecklistSchemaSerializer
from .builder import CollectionRequestBuilder
from .exporter import CollectionRequestExporter

log = logging.getLogger(__name__)


class ChecklistSchemaMixin:
    """
    Mixin that adds checklist schema management endpoints to a ViewSet.

    Provides:
    - GET /{pk}/checklist-schema/ - Export current schema as JSON
    - PUT /{pk}/checklist-schema/ - Update schema and rebuild CollectionRequest

    Requirements:
    - Parent ViewSet must return an object with a `collection_request` attribute
      or implement `get_collection_request(obj)` method
    - Optionally implement `get_schema_serializer_class()` to customize serializer

    Usage:
        class EEPProgramViewSet(ChecklistSchemaMixin, viewsets.ModelViewSet):
            ...
            def get_collection_request(self, obj):
                return obj.collection_request
    """

    schema_serializer_class = ChecklistSchemaSerializer
    schema_detail_route_kwargs = {"methods": ["get", "put"], "url_path": "checklist-schema"}

    def get_schema_serializer_class(self):
        """Return the serializer class for checklist schema."""
        return self.schema_serializer_class

    def get_collection_request(self, obj) -> Optional[Any]:
        """
        Get the CollectionRequest for the given object.

        Override this method to customize how the collection request is retrieved.

        Args:
            obj: The parent object (e.g., EEPProgram instance)

        Returns:
            CollectionRequest instance or None
        """
        return getattr(obj, "collection_request", None)

    def get_schema_context(self, obj) -> dict:
        """
        Get additional context for schema export/import.

        Override to provide custom context for the schema operations.

        Args:
            obj: The parent object

        Returns:
            Dictionary of context values
        """
        return {}

    @action(detail=True, methods=["get", "put"], url_path="checklist-schema")
    def checklist_schema(self, request, *args, **kwargs):
        """
        Export or update the checklist schema.

        GET: Export the current schema as JSON
        PUT: Update the schema and rebuild the CollectionRequest
        """
        obj = self.get_object()

        if request.method == "GET":
            return self._export_schema(request, obj)
        elif request.method == "PUT":
            return self._update_schema(request, obj)

    def _export_schema(self, request, obj) -> Response:
        """Export the current schema as JSON."""
        collection_request = self.get_collection_request(obj)

        if not collection_request:
            return Response(
                {"error": "No collection request found for this object."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            exporter = CollectionRequestExporter(collection_request)
            schema_data = exporter.export()

            # Serialize using the schema serializer for consistent format
            serializer_class = self.get_schema_serializer_class()
            serializer = serializer_class(data=schema_data)
            serializer.is_valid(raise_exception=True)

            return Response(serializer.validated_data)

        except Exception as e:
            log.exception(f"Error exporting schema: {e}")
            return Response(
                {"error": f"Failed to export schema: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _update_schema(self, request, obj) -> Response:
        """Update the schema and rebuild the CollectionRequest."""
        collection_request = self.get_collection_request(obj)

        # Validate schema data
        serializer_class = self.get_schema_serializer_class()
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        schema_data = serializer.validated_data

        try:
            # Get additional context
            context = self.get_schema_context(obj)

            # Build or rebuild the collection request
            builder = CollectionRequestBuilder()
            new_collection_request = builder.build(
                schema=schema_data,
                existing_request=collection_request,
                **context,
            )

            # Update the parent object's reference if needed
            if collection_request != new_collection_request:
                self._set_collection_request(obj, new_collection_request)

            # Export the updated schema
            exporter = CollectionRequestExporter(new_collection_request)
            exported_schema = exporter.export()

            return Response(exported_schema, status=status.HTTP_200_OK)

        except ValidationError:
            raise
        except Exception as e:
            log.exception(f"Error updating schema: {e}")
            return Response(
                {"error": f"Failed to update schema: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _set_collection_request(self, obj, collection_request):
        """
        Set the collection request on the parent object.

        Override this method to customize how the collection request is saved.

        Args:
            obj: The parent object
            collection_request: The new CollectionRequest instance
        """
        if hasattr(obj, "collection_request"):
            obj.collection_request = collection_request
            obj.save(update_fields=["collection_request"])


class ChecklistConsumerMixin:
    """
    Mixin that adds checklist consumer endpoints to a ViewSet.

    Provides:
    - GET /{pk}/checklist/ - Get checklist with sections, instruments, and answers
    - POST /{pk}/checklist/answers/ - Submit answer(s) to instruments
    - GET /{pk}/checklist/instruments/ - List all instruments
    - GET /{pk}/checklist/instruments/{instrument_id}/ - Get instrument detail

    Response Structure:
    The checklist endpoint returns a rich, section-organized structure:
    {
        "id": 123,
        "name": "Checklist Name",
        "description": "...",
        "sections": [
            {
                "name": "Section Name",
                "slug": "section-slug",
                "description": "...",
                "order": 0,
                "questions": [
                    {
                        "id": 1,
                        "measure_id": "question-slug",
                        "text": "Question text?",
                        "description": "...",
                        "help_text": "...",
                        "type": "multiple-choice",
                        "order": 0,
                        "is_required": true,
                        "is_visible": true,
                        "constraints": {"min": 0, "max": 100},
                        "responses": [
                            {"value": "Yes", "flags": {"comment_required": false}},
                            {"value": "No", "flags": {"is_considered_failure": true}}
                        ],
                        "conditions": [
                            {
                                "type": "instrument",
                                "source": "other-question",
                                "match_type": "match",
                                "values": ["Yes"]
                            }
                        ],
                        "answer": {
                            "id": 456,
                            "data": {"input": "Yes", "comment": "..."},
                            "date_created": "..."
                        }
                    }
                ]
            }
        ],
        "progress": {
            "total": 10,
            "answered": 5,
            "visible": 8,
            "required_answered": 4,
            "required_total": 6
        }
    }

    Requirements:
    - Parent ViewSet must implement these methods:
      - get_collection_request(obj): Return the CollectionRequest
      - get_collector(obj, user, user_role): Return a Collector instance
      - get_home_status(obj): Return the home_status (for answer context)

    The collector should implement:
      - get_instruments(active=True): Return filtered instruments
      - is_instrument_allowed(instrument): Check condition visibility
      - store(instrument, data, user): Store an answer
      - get_method(instrument): Get the method for constraints

    Usage:
        class HomeStatusViewSet(ChecklistConsumerMixin, viewsets.ModelViewSet):
            ...
            def get_collection_request(self, obj):
                return obj.eep_program.collection_request

            def get_collector(self, obj, user, user_role='rater'):
                return obj.get_collector(user_role=user_role, user=user)

            def get_home_status(self, obj):
                return obj
    """

    checklist_user_role_param = "user_role"
    checklist_default_user_role = "rater"

    def get_collection_request(self, obj) -> Optional[Any]:
        """
        Get the CollectionRequest for the given object.

        Must be implemented by the parent ViewSet.
        """
        raise NotImplementedError("Subclass must implement get_collection_request()")

    def get_collector(self, obj, user, user_role: str = "rater") -> Any:
        """
        Get a Collector instance for the given object.

        Must be implemented by the parent ViewSet.

        Args:
            obj: The parent object (e.g., HomeStatus instance)
            user: The request user
            user_role: User role ('rater', 'qa', etc.)

        Returns:
            A Collector instance
        """
        raise NotImplementedError("Subclass must implement get_collector()")

    def get_home_status(self, obj) -> Optional[Any]:
        """
        Get the home_status for answer context.

        Override this method if the object is not itself a home_status.

        Args:
            obj: The parent object

        Returns:
            Home status instance or None
        """
        return obj

    def get_user_role(self, request) -> str:
        """Get the user role from request parameters."""
        return request.query_params.get(
            self.checklist_user_role_param, self.checklist_default_user_role
        )

    def get_answer_serializer_class(self):
        """
        Return the serializer class for collected inputs.

        Override to use a custom serializer.
        """
        # Import here to avoid circular imports
        from django_input_collection.models import CollectedInput
        from rest_framework import serializers

        class DefaultCollectedInputSerializer(serializers.ModelSerializer):
            """Basic serializer for collected inputs."""

            class Meta:
                model = CollectedInput
                fields = (
                    "id",
                    "instrument",
                    "data",
                    "user",
                    "user_role",
                    "date_created",
                    "date_modified",
                )
                read_only_fields = ("id", "user", "date_created", "date_modified")

        return DefaultCollectedInputSerializer

    def get_instrument_serializer_class(self):
        """
        Return the serializer class for instruments.

        Override to use a custom serializer with additional fields.
        """
        from django_input_collection.models import CollectionInstrument
        from rest_framework import serializers

        class DefaultInstrumentSerializer(serializers.ModelSerializer):
            """Basic serializer for collection instruments."""

            is_required = serializers.SerializerMethodField()
            type_id = serializers.CharField(source="type.id", read_only=True)

            def get_is_required(self, obj):
                return obj.response_policy and obj.response_policy.required

            class Meta:
                model = CollectionInstrument
                fields = (
                    "id",
                    "measure",
                    "text",
                    "description",
                    "help",
                    "order",
                    "type_id",
                    "is_required",
                )

        return DefaultInstrumentSerializer

    @action(detail=True, methods=["get"], url_path="checklist")
    def checklist(self, request, *args, **kwargs):
        """
        Get the checklist with sections, instruments, and collected answers.

        Returns a rich, section-organized structure with:
        - Sections with metadata (name, slug, description, order)
        - Questions with all metadata, visibility, and conditions
        - Current answers for each question
        - Progress summary

        Query Parameters:
            user_role (str): User role context ('rater' or 'qa'), defaults to 'rater'

        Returns:
            Checklist with sections, questions, answers, and progress
        """
        obj = self.get_object()
        user_role = self.get_user_role(request)

        collection_request = self.get_collection_request(obj)
        if not collection_request:
            raise NotFound("No checklist found for this object.")

        try:
            collector = self.get_collector(obj, request.user, user_role)
        except Exception as e:
            raise PermissionDenied(str(e))

        # Build the rich response structure
        checklist_data = self._build_checklist_response(
            collection_request, collector, request.user, user_role
        )

        return Response(checklist_data)

    @action(detail=True, methods=["post"], url_path="checklist/answers")
    def checklist_answers(self, request, *args, **kwargs):
        """
        Submit answer(s) to checklist instruments.

        Accepts either a single answer or a list of answers.

        Request body (single):
            {
                "measure": "measure-id",
                "data": {"input": "value", "comment": "optional comment"},
                "user_role": "rater"
            }

        Request body (bulk):
            [
                {"measure": "measure-id-1", "data": {"input": "value1"}},
                {"measure": "measure-id-2", "data": {"input": "value2"}}
            ]

        Returns:
            Created collected input(s)
        """
        obj = self.get_object()
        is_bulk = isinstance(request.data, list)
        answers = request.data if is_bulk else [request.data]

        # Get user role from first answer or params
        user_role = answers[0].get("user_role") if answers else None
        user_role = user_role or self.get_user_role(request)

        try:
            collector = self.get_collector(obj, request.user, user_role)
        except Exception as e:
            raise PermissionDenied(str(e))

        home_status = self.get_home_status(obj)
        results = []
        errors = []

        for idx, answer_data in enumerate(answers):
            try:
                result = self._process_answer(
                    collector=collector,
                    answer_data=answer_data,
                    home_status=home_status,
                    user=request.user,
                    user_role=answer_data.get("user_role", user_role),
                )
                results.append(result)
            except ValidationError as e:
                errors.append({"index": idx, "errors": e.detail})
            except Exception as e:
                errors.append({"index": idx, "errors": str(e)})

        if errors and not results:
            # All failed
            return Response(
                {"errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = results if is_bulk else results[0] if results else None

        if errors:
            # Partial success
            return Response(
                {"data": response_data, "errors": errors},
                status=status.HTTP_207_MULTI_STATUS,
            )

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="checklist/instruments")
    def checklist_instruments(self, request, *args, **kwargs):
        """
        List all instruments for the checklist.

        Query Parameters:
            user_role (str): User role context ('rater' or 'qa'), defaults to 'rater'

        Returns:
            List of instruments with metadata
        """
        obj = self.get_object()
        user_role = self.get_user_role(request)

        collection_request = self.get_collection_request(obj)
        if not collection_request:
            raise NotFound("No checklist found for this object.")

        try:
            collector = self.get_collector(obj, request.user, user_role)
        except Exception as e:
            raise PermissionDenied(str(e))

        instruments = collector.get_instruments(active=True)

        # Serialize instruments with visibility info
        serializer_class = self.get_instrument_serializer_class()
        instrument_data = []

        for instrument in instruments:
            data = serializer_class(instrument).data
            data["is_visible"] = self._get_instrument_visibility(collector, instrument)
            instrument_data.append(data)

        return Response(instrument_data)

    @action(
        detail=True,
        methods=["get"],
        url_path=r"checklist/instruments/(?P<instrument_id>[^/.]+)",
    )
    def checklist_instrument_detail(self, request, instrument_id=None, *args, **kwargs):
        """
        Get detailed information about a specific instrument.

        Query Parameters:
            user_role (str): User role context ('rater' or 'qa'), defaults to 'rater'

        Returns:
            Instrument detail with constraints and valid_responses
        """
        obj = self.get_object()
        user_role = self.get_user_role(request)

        collection_request = self.get_collection_request(obj)
        if not collection_request:
            raise NotFound("No checklist found for this object.")

        try:
            collector = self.get_collector(obj, request.user, user_role)
        except Exception as e:
            raise PermissionDenied(str(e))

        # Find the instrument
        from django_input_collection.models import CollectionInstrument

        try:
            instrument = CollectionInstrument.objects.get(
                id=instrument_id, collection_request=collection_request
            )
        except CollectionInstrument.DoesNotExist:
            raise NotFound(f"Instrument {instrument_id} not found.")

        # Build detailed response
        serializer_class = self.get_instrument_serializer_class()
        data = serializer_class(instrument).data
        data["is_visible"] = self._get_instrument_visibility(collector, instrument)
        data["constraints"] = self._get_instrument_constraints(collector, instrument)
        data["valid_responses"] = self._get_valid_responses(instrument)

        return Response(data)

    def _build_checklist_response(self, collection_request, collector, user, user_role) -> dict:
        """
        Build the rich checklist response with sections and progress.

        Args:
            collection_request: The CollectionRequest instance
            collector: The Collector instance
            user: The request user
            user_role: User role string

        Returns:
            Dictionary with checklist data including sections and progress
        """
        from django_input_collection.models import CollectedInput, CollectionGroup

        # Get all instruments for this request
        all_instruments = list(collection_request.collectioninstrument_set.all().order_by("order"))

        # Build instrument lookup and collect answers
        instrument_by_measure = {i.measure_id: i for i in all_instruments}

        # Get all collected inputs for this collection request
        collected_inputs = (
            CollectedInput.objects.filter(collection_request=collection_request)
            .select_related("user")
            .order_by("-date_created")
        )

        # Map instrument_id -> most recent input
        input_by_instrument = {}
        for ci in collected_inputs:
            if ci.instrument_id not in input_by_instrument:
                input_by_instrument[ci.instrument_id] = ci

        # Get sections (groups)
        groups = CollectionGroup.objects.filter(collection_request=collection_request).order_by(
            "order"
        )

        # Build instrument -> group mapping
        instrument_to_group = {}
        for group in groups:
            for instrument in group.collectioninstrument_set.all():
                instrument_to_group[instrument.id] = group

        # Track progress
        progress = {
            "total": len(all_instruments),
            "answered": 0,
            "visible": 0,
            "required_total": 0,
            "required_answered": 0,
        }

        # Build sections
        sections_data = []
        ungrouped_questions = []

        # Process grouped instruments
        for group in groups:
            section_questions = []
            group_instruments = list(group.collectioninstrument_set.all().order_by("order"))

            for instrument in group_instruments:
                question_data = self._build_question_data(
                    instrument=instrument,
                    collector=collector,
                    collected_input=input_by_instrument.get(instrument.id),
                    instrument_by_measure=instrument_by_measure,
                    progress=progress,
                )
                section_questions.append(question_data)

            if section_questions:
                sections_data.append(
                    {
                        "name": group.name or "Untitled Section",
                        "slug": getattr(group, "slug", None)
                        or self._slugify(group.name or "section"),
                        "description": group.description or "",
                        "order": group.order or 0,
                        "questions": section_questions,
                    }
                )

        # Process ungrouped instruments
        for instrument in all_instruments:
            if instrument.id not in instrument_to_group:
                question_data = self._build_question_data(
                    instrument=instrument,
                    collector=collector,
                    collected_input=input_by_instrument.get(instrument.id),
                    instrument_by_measure=instrument_by_measure,
                    progress=progress,
                )
                ungrouped_questions.append(question_data)

        # Add ungrouped as "General" section if any
        if ungrouped_questions:
            sections_data.insert(
                0,
                {
                    "name": "General",
                    "slug": "general",
                    "description": "",
                    "order": -1,
                    "questions": ungrouped_questions,
                },
            )

        # Sort sections by order
        sections_data.sort(key=lambda s: s["order"])

        return {
            "id": collection_request.id,
            "name": getattr(collection_request, "name", None)
            or f"Checklist {collection_request.id}",
            "description": getattr(collection_request, "description", "") or "",
            "sections": sections_data,
            "progress": progress,
        }

    def _build_question_data(
        self, instrument, collector, collected_input, instrument_by_measure, progress
    ) -> dict:
        """
        Build the data structure for a single question.

        Args:
            instrument: The CollectionInstrument
            collector: The Collector instance
            collected_input: The most recent CollectedInput or None
            instrument_by_measure: Dict mapping measure_id to instrument
            progress: Progress dict to update

        Returns:
            Question data dictionary
        """
        # Get visibility
        is_visible = self._get_instrument_visibility(collector, instrument)

        # Get required status
        is_required = instrument.response_policy and instrument.response_policy.required

        # Update progress counters
        if is_visible:
            progress["visible"] += 1
        if is_required:
            progress["required_total"] += 1
        if collected_input:
            progress["answered"] += 1
            if is_required:
                progress["required_answered"] += 1

        # Build question data
        question_data = {
            "id": instrument.id,
            "measure_id": instrument.measure_id,
            "text": instrument.text or "",
            "description": instrument.description or "",
            "help_text": instrument.help or "",
            "type": instrument.type.id if instrument.type else "open",
            "order": instrument.order or 0,
            "is_required": is_required,
            "is_visible": is_visible,
            "constraints": self._get_instrument_constraints(collector, instrument),
            "responses": self._get_responses_with_flags(instrument),
            "conditions": self._get_conditions(instrument, instrument_by_measure),
            "answer": self._serialize_answer(collected_input) if collected_input else None,
        }

        return question_data

    def _get_responses_with_flags(self, instrument) -> Optional[list]:
        """Get responses with their flags for multiple-choice instruments."""
        if not instrument.suggested_responses.exists():
            return None

        responses = []
        for sr in instrument.suggested_responses.all():
            response_data = {"value": sr.data}

            # Try to get flags from bound response (application-specific)
            # This hook allows applications to add their own flag handling
            flags = self._get_response_flags(instrument, sr)
            if flags:
                response_data["flags"] = flags

            responses.append(response_data)

        return responses

    def _get_response_flags(self, instrument, suggested_response) -> Optional[dict]:
        """
        Get flags for a suggested response.

        Override this method to provide application-specific flag handling.

        Args:
            instrument: The CollectionInstrument
            suggested_response: The SuggestedResponse

        Returns:
            Dict of flags or None
        """
        # Default implementation - no flags
        # Applications should override this to check AxisBoundSuggestedResponse etc.
        return None

    def _get_conditions(self, instrument, instrument_by_measure) -> list:
        """
        Get conditions for an instrument in a user-friendly format.

        Args:
            instrument: The CollectionInstrument
            instrument_by_measure: Dict mapping measure_id to instrument

        Returns:
            List of condition dicts
        """
        conditions = []

        # Get conditions from instrument
        for condition in instrument.conditions.all():
            condition_data = self._serialize_condition(condition, instrument_by_measure)
            if condition_data:
                conditions.append(condition_data)

        return conditions

    def _serialize_condition(self, condition, instrument_by_measure) -> Optional[dict]:
        """
        Serialize a single condition.

        Args:
            condition: The Condition model instance
            instrument_by_measure: Dict mapping measure_id to instrument

        Returns:
            Condition dict or None
        """
        # Get the data_getter to determine condition type
        data_getter = getattr(condition, "data_getter", None)
        if not data_getter:
            return None

        # Parse data_getter to extract type and source
        # Format: "type:source" e.g., "instrument:measure-id" or "simulation:path"
        if ":" in data_getter:
            cond_type, source = data_getter.split(":", 1)
        else:
            # Assume instrument if no prefix
            cond_type = "instrument"
            source = data_getter

        # Build condition data
        condition_data = {
            "type": cond_type,
            "source": source,
            "match_type": getattr(condition, "match_type", "match") or "match",
            "values": list(condition.match_data)
            if hasattr(condition, "match_data") and condition.match_data
            else [],
        }

        return condition_data

    def _serialize_answer(self, collected_input) -> dict:
        """
        Serialize a collected input as an answer.

        Args:
            collected_input: The CollectedInput instance

        Returns:
            Answer dict
        """
        return {
            "id": collected_input.id,
            "data": collected_input.data,
            "user_id": collected_input.user_id,
            "user_role": collected_input.user_role,
            "date_created": collected_input.date_created.isoformat()
            if collected_input.date_created
            else None,
            "date_modified": collected_input.date_modified.isoformat()
            if collected_input.date_modified
            else None,
        }

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-safe slug."""
        import re

        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:100]

    def _get_instrument_visibility(self, collector, instrument) -> Optional[bool]:
        """Get instrument visibility based on conditions."""
        try:
            return collector.is_instrument_allowed(instrument)
        except Exception:
            return None

    def _get_instrument_constraints(self, collector, instrument) -> Optional[dict]:
        """Get constraints for numeric instruments."""
        try:
            method = collector.get_method(instrument)
            if hasattr(method, "get_constraints"):
                return method.get_constraints()
        except Exception:
            pass
        return None

    def _get_valid_responses(self, instrument) -> Optional[list]:
        """Get valid responses for multiple-choice instruments."""
        if not instrument.suggested_responses.exists():
            return None

        return [{"value": r.data} for r in instrument.suggested_responses.all()]

    def _process_answer(
        self, collector, answer_data: dict, home_status, user, user_role: str
    ) -> dict:
        """
        Process a single answer submission.

        Args:
            collector: The collector instance
            answer_data: Answer data dict with measure and data
            home_status: The home_status for context
            user: The user submitting the answer
            user_role: User role

        Returns:
            Serialized collected input

        Raises:
            ValidationError: If validation fails
        """
        measure_id = answer_data.get("measure")
        if not measure_id:
            raise ValidationError({"measure": "This field is required."})

        data_payload = answer_data.get("data", {})
        if not data_payload:
            raise ValidationError({"data": "This field is required."})

        # Get instrument from measure
        instrument = collector.get_instrument(measure_id)
        if not instrument:
            raise ValidationError({"measure": f"No instrument found for measure '{measure_id}'."})

        # Find existing input to update
        from django_input_collection.models import CollectedInput

        existing_input = CollectedInput.objects.filter(instrument=instrument).first()

        # Store using collector
        collected_input = collector.store(
            instrument=instrument,
            data=data_payload,
            instance=existing_input,
            user=user,
        )

        # Serialize result
        answer_serializer_class = self.get_answer_serializer_class()
        return answer_serializer_class(collected_input).data
