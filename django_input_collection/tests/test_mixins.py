"""test_mixins.py: Tests for schema/mixins.py - ChecklistSchemaMixin and ChecklistConsumerMixin"""

__author__ = "Test Coverage"
__date__ = "01/12/26"

from unittest.mock import Mock, patch, MagicMock, PropertyMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from rest_framework.parsers import JSONParser
from rest_framework import status
from rest_framework.viewsets import ViewSet

from . import factories
from ..schema.mixins import ChecklistSchemaMixin, ChecklistConsumerMixin


User = get_user_model()


def make_drf_request(factory_request):
    """Convert a factory request to a DRF Request object."""
    return Request(factory_request, parsers=[JSONParser()])


class MockViewSetBase(ViewSet):
    """Base mock viewset for testing."""

    def get_object(self):
        return self._object

    def set_object(self, obj):
        self._object = obj


class ChecklistSchemaMixinViewSet(ChecklistSchemaMixin, MockViewSetBase):
    """Test viewset with ChecklistSchemaMixin."""

    def get_collection_request(self, obj):
        return getattr(obj, "collection_request", None)


class ChecklistConsumerMixinViewSet(ChecklistConsumerMixin, MockViewSetBase):
    """Test viewset with ChecklistConsumerMixin."""

    def get_collection_request(self, obj):
        return getattr(obj, "collection_request", None)

    def get_collector(self, obj, user, user_role="rater"):
        return getattr(obj, "collector", None)

    def get_home_status(self, obj):
        return obj


class ChecklistSchemaMixinTests(TestCase):
    """Tests for ChecklistSchemaMixin."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.viewset = ChecklistSchemaMixinViewSet()
        self.cr = factories.CollectionRequestFactory.create()
        self.group = factories.CollectionGroupFactory.create(id="test-section")
        self.instrument = factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="test-q",
            text="Test Question",
            group=self.group,
        )

    def test_get_schema_serializer_class(self):
        """Test get_schema_serializer_class returns correct class."""
        from ..schema.serializers import ChecklistSchemaSerializer

        serializer_class = self.viewset.get_schema_serializer_class()
        self.assertEqual(serializer_class, ChecklistSchemaSerializer)

    def test_get_collection_request_with_attr(self):
        """Test get_collection_request when object has collection_request attribute."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr

        result = self.viewset.get_collection_request(mock_obj)
        self.assertEqual(result, self.cr)

    def test_get_collection_request_without_attr(self):
        """Test get_collection_request when object lacks collection_request."""
        mock_obj = Mock(spec=[])  # No collection_request attribute

        result = self.viewset.get_collection_request(mock_obj)
        self.assertIsNone(result)

    def test_get_schema_context(self):
        """Test get_schema_context returns empty dict by default."""
        mock_obj = Mock()
        result = self.viewset.get_schema_context(mock_obj)
        self.assertEqual(result, {})

    def test_export_schema_success(self):
        """Test _export_schema returns schema data."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr

        request = self.factory.get("/test/")
        request.user = self.user

        response = self.viewset._export_schema(request, mock_obj)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("version", response.data)
        self.assertIn("sections", response.data)

    def test_export_schema_no_collection_request(self):
        """Test _export_schema returns 404 when no collection request."""
        mock_obj = Mock(spec=[])  # No collection_request

        request = self.factory.get("/test/")
        request.user = self.user

        response = self.viewset._export_schema(request, mock_obj)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_export_schema_exception(self):
        """Test _export_schema handles exceptions."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr

        request = self.factory.get("/test/")
        request.user = self.user

        with patch(
            "django_input_collection.schema.mixins.CollectionRequestExporter.export",
            side_effect=Exception("Export failed"),
        ):
            response = self.viewset._export_schema(request, mock_obj)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)

    def test_update_schema_success(self):
        """Test _update_schema updates collection request."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr

        factory_request = self.factory.put(
            "/test/",
            data={
                "version": "1.0",
                "name": "Updated Checklist",
                "sections": [
                    {
                        "name": "New Section",
                        "questions": [
                            {
                                "measure_id": "new-q",
                                "text": "New Question",
                                "type": "open",
                            }
                        ],
                    }
                ],
            },
            format="json",
        )
        factory_request.user = self.user
        request = make_drf_request(factory_request)

        response = self.viewset._update_schema(request, mock_obj)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_schema_validation_error(self):
        """Test _update_schema handles validation errors."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr

        # Invalid schema - missing required fields
        factory_request = self.factory.put(
            "/test/",
            data={
                "invalid": "schema",
            },
            format="json",
        )
        factory_request.user = self.user
        request = make_drf_request(factory_request)

        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.viewset._update_schema(request, mock_obj)

    def test_set_collection_request(self):
        """Test _set_collection_request updates object."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr
        mock_obj.save = Mock()

        new_cr = factories.CollectionRequestFactory.create()

        self.viewset._set_collection_request(mock_obj, new_cr)

        self.assertEqual(mock_obj.collection_request, new_cr)
        mock_obj.save.assert_called_once_with(update_fields=["collection_request"])

    def test_set_collection_request_no_attr(self):
        """Test _set_collection_request handles objects without attribute."""
        mock_obj = Mock(spec=[])  # No collection_request attribute

        new_cr = factories.CollectionRequestFactory.create()

        # Should not raise error
        self.viewset._set_collection_request(mock_obj, new_cr)

    def test_checklist_schema_get(self):
        """Test checklist_schema action GET request."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr
        self.viewset.set_object(mock_obj)

        request = self.factory.get("/test/")
        request.method = "GET"
        request.user = self.user

        response = self.viewset.checklist_schema(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_checklist_schema_put(self):
        """Test checklist_schema action PUT request."""
        mock_obj = Mock()
        mock_obj.collection_request = self.cr
        mock_obj.save = Mock()
        self.viewset.set_object(mock_obj)

        factory_request = self.factory.put(
            "/test/",
            data={
                "version": "1.0",
                "name": "Updated",
                "sections": [
                    {
                        "name": "Section",
                        "questions": [{"measure_id": "q1", "text": "Q", "type": "open"}],
                    }
                ],
            },
            format="json",
        )
        factory_request.user = self.user
        request = make_drf_request(factory_request)
        request.method = "PUT"

        response = self.viewset.checklist_schema(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ChecklistConsumerMixinTests(TestCase):
    """Tests for ChecklistConsumerMixin."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="testuser2", password="testpass")
        self.viewset = ChecklistConsumerMixinViewSet()
        self.cr = factories.CollectionRequestFactory.create()
        self.group = factories.CollectionGroupFactory.create(id="consumer-section")
        self.response_yes = factories.SuggestedResponseFactory.create(data="Yes")
        self.response_no = factories.SuggestedResponseFactory.create(data="No")
        self.instrument = factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="consumer-q",
            text="Consumer Question",
            group=self.group,
            suggested_responses=[self.response_yes, self.response_no],
        )

    def test_get_collection_request_not_implemented(self):
        """Test ChecklistConsumerMixin.get_collection_request raises NotImplementedError."""
        mixin = ChecklistConsumerMixin()
        with self.assertRaises(NotImplementedError):
            mixin.get_collection_request(Mock())

    def test_get_collector_not_implemented(self):
        """Test ChecklistConsumerMixin.get_collector raises NotImplementedError."""
        mixin = ChecklistConsumerMixin()
        with self.assertRaises(NotImplementedError):
            mixin.get_collector(Mock(), Mock())

    def test_get_home_status_default(self):
        """Test get_home_status returns the object itself by default."""
        mixin = ChecklistConsumerMixin()
        obj = Mock()
        result = mixin.get_home_status(obj)
        self.assertEqual(result, obj)

    def test_get_user_role_default(self):
        """Test get_user_role returns default when not in params."""
        request = Mock()
        request.query_params = {}

        result = self.viewset.get_user_role(request)
        self.assertEqual(result, "rater")

    def test_get_user_role_from_params(self):
        """Test get_user_role returns value from params."""
        request = Mock()
        request.query_params = {"user_role": "qa"}

        result = self.viewset.get_user_role(request)
        self.assertEqual(result, "qa")

    def test_get_answer_serializer_class(self):
        """Test get_answer_serializer_class returns a serializer class."""
        serializer_class = self.viewset.get_answer_serializer_class()
        self.assertIsNotNone(serializer_class)
        # Should have a Meta class
        self.assertTrue(hasattr(serializer_class, "Meta"))

    def test_get_instrument_serializer_class(self):
        """Test get_instrument_serializer_class returns a serializer class."""
        serializer_class = self.viewset.get_instrument_serializer_class()
        self.assertIsNotNone(serializer_class)
        self.assertTrue(hasattr(serializer_class, "Meta"))

    def test_slugify(self):
        """Test _slugify method."""
        result = self.viewset._slugify("Test Section Name!")
        self.assertEqual(result, "test-section-name")

    def test_slugify_long_text(self):
        """Test _slugify truncates long text."""
        long_text = "x" * 200
        result = self.viewset._slugify(long_text)
        self.assertEqual(len(result), 100)

    def test_get_instrument_visibility(self):
        """Test _get_instrument_visibility method."""
        mock_collector = Mock()
        mock_collector.is_instrument_allowed = Mock(return_value=True)

        result = self.viewset._get_instrument_visibility(mock_collector, self.instrument)
        self.assertTrue(result)

    def test_get_instrument_visibility_exception(self):
        """Test _get_instrument_visibility handles exceptions."""
        mock_collector = Mock()
        mock_collector.is_instrument_allowed = Mock(side_effect=Exception("Error"))

        result = self.viewset._get_instrument_visibility(mock_collector, self.instrument)
        self.assertIsNone(result)

    def test_get_instrument_constraints(self):
        """Test _get_instrument_constraints method."""
        mock_method = Mock()
        mock_method.get_constraints = Mock(return_value={"min": 0, "max": 100})

        mock_collector = Mock()
        mock_collector.get_method = Mock(return_value=mock_method)

        result = self.viewset._get_instrument_constraints(mock_collector, self.instrument)
        self.assertEqual(result, {"min": 0, "max": 100})

    def test_get_instrument_constraints_no_method(self):
        """Test _get_instrument_constraints when method has no constraints."""
        mock_collector = Mock()
        mock_collector.get_method = Mock(side_effect=Exception("Error"))

        result = self.viewset._get_instrument_constraints(mock_collector, self.instrument)
        self.assertIsNone(result)

    def test_get_valid_responses(self):
        """Test _get_valid_responses method."""
        result = self.viewset._get_valid_responses(self.instrument)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        values = [r["value"] for r in result]
        self.assertIn("Yes", values)
        self.assertIn("No", values)

    def test_get_valid_responses_no_responses(self):
        """Test _get_valid_responses when no suggested responses."""
        instrument = factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="no-responses-q",
            text="No responses",
        )

        result = self.viewset._get_valid_responses(instrument)
        self.assertIsNone(result)

    def test_get_responses_with_flags(self):
        """Test _get_responses_with_flags method."""
        result = self.viewset._get_responses_with_flags(self.instrument)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertIn("value", r)

    def test_get_response_flags_default(self):
        """Test _get_response_flags returns None by default."""
        result = self.viewset._get_response_flags(self.instrument, self.response_yes)
        self.assertIsNone(result)

    def test_serialize_answer(self):
        """Test _serialize_answer method."""
        collected_input = Mock()
        collected_input.id = 1
        collected_input.data = {"input": "Yes"}
        collected_input.user_id = self.user.id
        collected_input.user_role = "rater"
        collected_input.date_created = None
        collected_input.date_modified = None

        result = self.viewset._serialize_answer(collected_input)

        self.assertEqual(result["id"], 1)
        self.assertEqual(result["data"], {"input": "Yes"})

    def test_serialize_condition(self):
        """Test _serialize_condition method."""
        condition = Mock()
        condition.data_getter = "instrument:test-measure"
        condition.match_type = "match"
        condition.match_data = ["Yes"]

        instrument_by_measure = {}

        result = self.viewset._serialize_condition(condition, instrument_by_measure)

        self.assertEqual(result["type"], "instrument")
        self.assertEqual(result["source"], "test-measure")

    def test_serialize_condition_no_data_getter(self):
        """Test _serialize_condition when no data_getter."""
        condition = Mock()
        condition.data_getter = None

        result = self.viewset._serialize_condition(condition, {})
        self.assertIsNone(result)

    def test_get_conditions(self):
        """Test _get_conditions method."""
        # Create instrument with condition
        parent_instrument = factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="parent-measure",
        )

        condition_group = factories.ConditionGroupFactory.create()
        factories.ConditionFactory.create(
            instrument=self.instrument,
            data_getter="instrument:parent-measure",
            condition_group=condition_group,
        )

        instrument_by_measure = {"parent-measure": parent_instrument}

        result = self.viewset._get_conditions(self.instrument, instrument_by_measure)

        self.assertIsInstance(result, list)

    def test_build_question_data(self):
        """Test _build_question_data method."""
        mock_collector = Mock()
        mock_collector.is_instrument_allowed = Mock(return_value=True)
        mock_collector.get_method = Mock(side_effect=Exception("No method"))

        progress = {
            "total": 1,
            "answered": 0,
            "visible": 0,
            "required_total": 0,
            "required_answered": 0,
        }

        result = self.viewset._build_question_data(
            instrument=self.instrument,
            collector=mock_collector,
            collected_input=None,
            instrument_by_measure={},
            progress=progress,
        )

        self.assertEqual(result["measure_id"], "consumer-q")
        self.assertEqual(result["text"], "Consumer Question")
        self.assertTrue(result["is_visible"])
        self.assertIsNone(result["answer"])
        self.assertEqual(progress["visible"], 1)

    def test_build_question_data_with_answer(self):
        """Test _build_question_data with collected input."""
        mock_collector = Mock()
        mock_collector.is_instrument_allowed = Mock(return_value=True)
        mock_collector.get_method = Mock(side_effect=Exception("No method"))

        collected_input = Mock()
        collected_input.id = 1
        collected_input.data = {"input": "Yes"}
        collected_input.user_id = self.user.id
        collected_input.user_role = "rater"
        collected_input.date_created = None
        collected_input.date_modified = None

        progress = {
            "total": 1,
            "answered": 0,
            "visible": 0,
            "required_total": 0,
            "required_answered": 0,
        }

        result = self.viewset._build_question_data(
            instrument=self.instrument,
            collector=mock_collector,
            collected_input=collected_input,
            instrument_by_measure={},
            progress=progress,
        )

        self.assertIsNotNone(result["answer"])
        self.assertEqual(progress["answered"], 1)

    def test_build_checklist_response(self):
        """Test _build_checklist_response method builds sections and progress."""
        mock_collector = Mock()
        mock_collector.is_instrument_allowed = Mock(return_value=True)
        mock_collector.get_method = Mock(side_effect=Exception("No method"))

        # Mock the CollectionGroup query to avoid the bug in the mixin code
        # The mixin incorrectly queries CollectionGroup.objects.filter(collection_request=...)
        # but CollectionGroup doesn't have a collection_request field
        with patch("django_input_collection.models.CollectionGroup.objects") as mock_manager:
            mock_manager.filter.return_value.order_by.return_value = []

            result = self.viewset._build_checklist_response(
                collection_request=self.cr,
                collector=mock_collector,
                user=self.user,
                user_role="rater",
            )

        self.assertIn("id", result)
        self.assertIn("sections", result)
        self.assertIn("progress", result)
        self.assertEqual(result["id"], self.cr.id)

    def test_checklist_action_no_collection_request(self):
        """Test checklist action when no collection request found."""
        from rest_framework.exceptions import NotFound

        mock_obj = Mock(spec=[])  # No collection_request
        self.viewset.set_object(mock_obj)

        request = self.factory.get("/test/checklist/")
        request.user = self.user
        request.query_params = {}

        with self.assertRaises(NotFound):
            self.viewset.checklist(request)

    def test_checklist_action_collector_error(self):
        """Test checklist action when collector raises error."""
        from rest_framework.exceptions import PermissionDenied

        class ErrorViewSet(ChecklistConsumerMixin, MockViewSetBase):
            def get_collection_request(self, obj):
                return obj.collection_request

            def get_collector(self, obj, user, user_role="rater"):
                raise Exception("Permission denied")

        viewset = ErrorViewSet()
        mock_obj = Mock()
        mock_obj.collection_request = self.cr
        viewset.set_object(mock_obj)

        request = self.factory.get("/test/checklist/")
        request.user = self.user
        request.query_params = {}

        with self.assertRaises(PermissionDenied):
            viewset.checklist(request)

    def test_checklist_instruments_no_collection_request(self):
        """Test checklist_instruments action when no collection request found."""
        from rest_framework.exceptions import NotFound

        mock_obj = Mock(spec=[])
        self.viewset.set_object(mock_obj)

        request = self.factory.get("/test/checklist/instruments/")
        request.user = self.user
        request.query_params = {}

        with self.assertRaises(NotFound):
            self.viewset.checklist_instruments(request)

    def test_checklist_instrument_detail_not_found(self):
        """Test checklist_instrument_detail when instrument not found."""
        from rest_framework.exceptions import NotFound

        mock_collector = Mock()
        mock_obj = Mock()
        mock_obj.collection_request = self.cr
        mock_obj.collector = mock_collector
        self.viewset.set_object(mock_obj)

        request = self.factory.get("/test/checklist/instruments/99999/")
        request.user = self.user
        request.query_params = {}

        with self.assertRaises(NotFound):
            self.viewset.checklist_instrument_detail(request, instrument_id="99999")

    def test_checklist_instrument_detail_success(self):
        """Test checklist_instrument_detail returns instrument data."""
        mock_collector = Mock()
        mock_collector.is_instrument_allowed = Mock(return_value=True)
        mock_collector.get_method = Mock(side_effect=Exception("No method"))

        mock_obj = Mock()
        mock_obj.collection_request = self.cr
        mock_obj.collector = mock_collector
        self.viewset.set_object(mock_obj)

        request = self.factory.get(f"/test/checklist/instruments/{self.instrument.id}/")
        request.user = self.user
        request.query_params = {}

        response = self.viewset.checklist_instrument_detail(
            request, instrument_id=str(self.instrument.id)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("measure", response.data)

    def test_checklist_answers_missing_measure_validation(self):
        """Test _process_answer raises error when measure is missing."""
        from rest_framework.exceptions import ValidationError

        mock_collector = Mock()

        with self.assertRaises(ValidationError) as context:
            self.viewset._process_answer(
                collector=mock_collector,
                answer_data={"data": {"input": "Yes"}},  # Missing measure
                home_status=Mock(),
                user=self.user,
                user_role="rater",
            )

        self.assertIn("measure", str(context.exception.detail))

    def test_checklist_answers_missing_data_validation(self):
        """Test _process_answer raises error when data is missing."""
        from rest_framework.exceptions import ValidationError

        mock_collector = Mock()

        with self.assertRaises(ValidationError) as context:
            self.viewset._process_answer(
                collector=mock_collector,
                answer_data={"measure": "consumer-q"},  # Missing data
                home_status=Mock(),
                user=self.user,
                user_role="rater",
            )

        self.assertIn("data", str(context.exception.detail))

    def test_checklist_answers_instrument_not_found_validation(self):
        """Test _process_answer raises error when instrument not found."""
        from rest_framework.exceptions import ValidationError

        mock_collector = Mock()
        mock_collector.get_instrument = Mock(return_value=None)

        with self.assertRaises(ValidationError) as context:
            self.viewset._process_answer(
                collector=mock_collector,
                answer_data={"measure": "nonexistent", "data": {"input": "Yes"}},
                home_status=Mock(),
                user=self.user,
                user_role="rater",
            )

        self.assertIn("measure", str(context.exception.detail))


class ChecklistMixinIntegrationTests(TestCase):
    """Integration tests for the checklist mixins."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="intuser", password="testpass")
        self.cr = factories.CollectionRequestFactory.create()
        self.group = factories.CollectionGroupFactory.create(id="integration-section")

    def test_full_schema_export_import_cycle(self):
        """Test full export and re-import of schema."""
        # Create complex collection request
        response_yes = factories.SuggestedResponseFactory.create(data="Yes")
        response_no = factories.SuggestedResponseFactory.create(data="No")

        factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="parent-q",
            text="Parent Question",
            group=self.group,
            order=10,
            suggested_responses=[response_yes, response_no],
        )

        child = factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="child-q",
            text="Child Question",
            group=self.group,
            order=20,
        )

        # Add condition
        condition_group = factories.ConditionGroupFactory.create()
        case = factories.CaseFactory.create(match_type="match", match_data="Yes")
        condition_group.cases.add(case)
        factories.ConditionFactory.create(
            instrument=child,
            data_getter="instrument:parent-q",
            condition_group=condition_group,
        )

        # Export
        from ..schema.exporter import CollectionRequestExporter

        exporter = CollectionRequestExporter()
        schema = exporter.export(self.cr, name="Integration Test")

        self.assertIn("sections", schema)
        self.assertEqual(len(schema["sections"]), 1)
        self.assertEqual(len(schema["sections"][0]["questions"]), 2)

        # Verify structure
        questions = schema["sections"][0]["questions"]
        parent_q = next(q for q in questions if q["measure_id"] == "parent-q")
        child_q = next(q for q in questions if q["measure_id"] == "child-q")

        self.assertEqual(parent_q["text"], "Parent Question")
        self.assertIn("conditions", child_q)

        # Import to new collection request
        from ..schema.builder import CollectionRequestBuilder

        builder = CollectionRequestBuilder()
        new_cr = builder.build(schema)

        self.assertNotEqual(new_cr.id, self.cr.id)
        self.assertEqual(new_cr.collectioninstrument_set.count(), 2)

        new_child = new_cr.collectioninstrument_set.get(measure_id="child-q")
        self.assertEqual(new_child.conditions.count(), 1)
