"""test_coverage.py: Additional tests to improve code coverage for low-coverage modules"""

__author__ = "Test Coverage"
__date__ = "01/12/26"

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

from . import factories


class EncoderTests(TestCase):
    """Tests for django_input_collection/encoders.py"""

    def test_encode_model_instance(self):
        """Test encoding a Django model instance."""
        from ..encoders import CollectionSpecificationJSONEncoder
        import json

        cr = factories.CollectionRequestFactory.create()
        encoder = CollectionSpecificationJSONEncoder()

        # Test that model instance is converted to dict
        result = encoder.default(cr)
        self.assertIsInstance(result, dict)
        self.assertIn("id", result)

    def test_encode_lazy_string(self):
        """Test encoding lazy string (Promise)."""
        from ..encoders import CollectionSpecificationJSONEncoder
        from django.utils.functional import lazy

        encoder = CollectionSpecificationJSONEncoder()
        lazy_str = lazy(lambda: "test string", str)()

        result = encoder.default(lazy_str)
        self.assertEqual(result, "test string")

    def test_encode_regular_types_fallback(self):
        """Test that regular types fall back to parent encoder."""
        from ..encoders import CollectionSpecificationJSONEncoder
        import json

        encoder = CollectionSpecificationJSONEncoder()

        # Test with a type that requires fallback
        from datetime import datetime

        dt = datetime.now()
        # The parent DjangoJSONEncoder handles datetime
        result = encoder.default(dt)
        self.assertIsInstance(result, str)


class CompatTests(TestCase):
    """Tests for django_input_collection/compat.py"""

    def test_userdict_import(self):
        """Test that UserDict can be imported."""
        from ..compat import UserDict

        self.assertIsNotNone(UserDict)

        # Test that it can be instantiated
        ud = UserDict()
        ud["key"] = "value"
        self.assertEqual(ud["key"], "value")


class FeaturesTests(TestCase):
    """Tests for django_input_collection/features.py"""

    def test_rest_framework_feature(self):
        """Test rest_framework feature detection."""
        from .. import features

        # rest_framework should be available in tests
        self.assertIsNotNone(features.rest_framework)


class ModelUtilsTests(TestCase):
    """Tests for django_input_collection/models/utils.py"""

    def test_lazy_clone(self):
        """Test lazy_clone function."""
        from ..models.utils import lazy_clone

        cr = factories.CollectionRequestFactory.create(
            max_instrument_inputs_per_user=5,
            max_instrument_inputs=10,
        )

        cloned = lazy_clone(cr)

        self.assertNotEqual(cloned.id, cr.id)
        self.assertEqual(cloned.max_instrument_inputs_per_user, 5)
        self.assertEqual(cloned.max_instrument_inputs, 10)

    def test_lazy_clone_with_updates(self):
        """Test lazy_clone with update kwargs."""
        from ..models.utils import lazy_clone

        cr = factories.CollectionRequestFactory.create(max_instrument_inputs=10)

        cloned = lazy_clone(cr, max_instrument_inputs=20)

        self.assertNotEqual(cloned.id, cr.id)
        self.assertEqual(cloned.max_instrument_inputs, 20)

    def test_lazy_clone_with_excludes(self):
        """Test lazy_clone with custom excludes."""
        from ..models.utils import lazy_clone

        cr = factories.CollectionRequestFactory.create()

        cloned = lazy_clone(cr, exclude=["max_instrument_inputs_per_user"])

        self.assertNotEqual(cloned.id, cr.id)

    def test_isolate_response_policy_already_isolated(self):
        """Test isolate_response_policy when policy is already isolated."""
        from ..models.utils import isolate_response_policy

        policy = factories.ResponsePolicyFactory.create(nickname="isolated-policy")
        instrument = factories.CollectionInstrumentFactory.create(response_policy=policy)

        original_policy_id = instrument.response_policy_id

        # Policy is only used by this instrument, so no clone should happen
        isolate_response_policy(instrument)
        instrument.refresh_from_db()

        self.assertEqual(instrument.response_policy_id, original_policy_id)

    def test_isolate_response_policy_shared(self):
        """Test isolate_response_policy when policy is shared."""
        from ..models.utils import isolate_response_policy

        policy = factories.ResponsePolicyFactory.create(nickname="shared-policy")
        instrument1 = factories.CollectionInstrumentFactory.create(response_policy=policy)
        instrument2 = factories.CollectionInstrumentFactory.create(response_policy=policy)

        original_policy_id = instrument1.response_policy_id

        # Policy is used by multiple instruments, should be cloned
        isolate_response_policy(instrument1)
        instrument1.refresh_from_db()

        self.assertNotEqual(instrument1.response_policy_id, original_policy_id)
        self.assertEqual(instrument2.response_policy_id, original_policy_id)

    def test_clone_response_policy(self):
        """Test clone_response_policy function."""
        from ..models.utils import clone_response_policy

        original = factories.ResponsePolicyFactory.create(
            nickname="original",
            restrict=True,
            multiple=False,
            required=True,
        )

        cloned = clone_response_policy(original)

        self.assertNotEqual(cloned.id, original.id)
        self.assertEqual(cloned.restrict, original.restrict)
        self.assertEqual(cloned.multiple, original.multiple)
        self.assertEqual(cloned.required, original.required)

    def test_clone_response_policy_with_isolate(self):
        """Test clone_response_policy with isolate flag."""
        from ..models.utils import clone_response_policy

        original = factories.ResponsePolicyFactory.create(
            nickname="original2",
            is_singleton=False,
        )

        cloned = clone_response_policy(original, isolate=True)

        self.assertTrue(cloned.is_singleton)

    def test_clone_collection_request(self):
        """Test clone_collection_request function."""
        from ..models.utils import clone_collection_request
        from ..models import Condition, Case, ConditionGroup

        cr = factories.CollectionRequestFactory.create()
        group = factories.CollectionGroupFactory.create(id="test-group")
        response = factories.SuggestedResponseFactory.create(data="Yes")

        instrument = factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            group=group,
            suggested_responses=[response],
        )

        # Add a condition
        condition_group = factories.ConditionGroupFactory.create()
        factories.ConditionFactory.create(
            instrument=instrument,
            data_getter="instrument:test-measure",
            condition_group=condition_group,
        )

        cloned = clone_collection_request(cr)

        self.assertNotEqual(cloned.id, cr.id)
        self.assertEqual(cloned.collectioninstrument_set.count(), 1)

        cloned_instrument = cloned.collectioninstrument_set.first()
        self.assertNotEqual(cloned_instrument.id, instrument.id)
        self.assertEqual(cloned_instrument.conditions.count(), 1)

    def test_condition_node_str(self):
        """Test ConditionNode string representation."""
        from ..models.utils import ConditionNode

        node = ConditionNode()
        result = str(node)
        self.assertEqual(result, "")

    def test_condition_node_with_children(self):
        """Test ConditionNode with children."""
        from ..models.utils import ConditionNode

        node = ConditionNode()
        node.children = ["a", "b"]
        node.connector = ", "

        result = str(node)
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_flatten_empty(self):
        """Test flatten with empty list."""
        from ..models.utils import flatten

        result = flatten([])
        self.assertEqual(result, [])

    def test_flatten_nested(self):
        """Test flatten with nested iterable."""
        from ..models.utils import flatten

        result = flatten([[1, 2], [3, 4]])
        self.assertEqual(sorted(result), [1, 2, 3, 4])


class ResolverTests(TestCase):
    """Tests for django_input_collection/collection/resolvers.py"""

    def setUp(self):
        self.cr = factories.CollectionRequestFactory.create()
        self.instrument = factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="test-measure",
        )

    def test_resolve_unknown_spec(self):
        """Test resolve with unknown spec raises ValueError."""
        from ..collection.resolvers import resolve

        with self.assertRaises(ValueError):
            resolve(self.instrument, "unknown:spec")

    def test_resolve_unknown_spec_no_raise(self):
        """Test resolve with unknown spec and raise_exception=False."""
        from ..collection.resolvers import resolve

        result = resolve(self.instrument, "unknown:spec", raise_exception=False)
        self.assertEqual(result, (None, {}, None))

    def test_instrument_resolver_by_pk(self):
        """Test InstrumentResolver with pk lookup."""
        from ..collection.resolvers import InstrumentResolver

        # Create another instrument to look up
        target_instrument = factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="target-measure",
        )

        resolver = InstrumentResolver()
        result = resolver.apply(f"instrument:{target_instrument.pk}")

        self.assertIsNotNone(result)
        self.assertIn("parent_pk", result)

    def test_instrument_resolver_by_measure(self):
        """Test InstrumentResolver with measure_id lookup."""
        from ..collection.resolvers import InstrumentResolver

        resolver = InstrumentResolver()
        result = resolver.apply("instrument:test-measure")

        self.assertIsNotNone(result)
        self.assertIn("measure", result)

    def test_instrument_resolver_resolve(self):
        """Test InstrumentResolver.resolve method."""
        from ..collection.resolvers import InstrumentResolver

        factories.CollectionInstrumentFactory.create(
            collection_request=self.cr,
            measure__id="target-for-resolve",
        )

        resolver = InstrumentResolver()
        result = resolver.resolve(
            instrument=self.instrument,
            measure="target-for-resolve",
        )

        self.assertIn("data", result)
        self.assertIn("suggested_values", result)

    def test_attribute_resolver(self):
        """Test AttributeResolver pattern matching."""
        from ..collection.resolvers import AttributeResolver

        resolver = AttributeResolver()
        result = resolver.apply("attr:some.path.here")

        self.assertIsNotNone(result)
        self.assertIn("dotted_path", result)

    def test_attribute_resolver_resolve_simple(self):
        """Test AttributeResolver.resolve with simple path."""
        from ..collection.resolvers import AttributeResolver

        resolver = AttributeResolver()

        # Test with instrument's measure_id attribute
        result = resolver.resolve(
            instrument=self.instrument,
            dotted_path="measure_id",
        )

        self.assertIn("data", result)
        self.assertEqual(result["data"], "test-measure")

    def test_attribute_resolver_resolve_dotted_path(self):
        """Test AttributeResolver.resolve with dotted path."""
        from ..collection.resolvers import AttributeResolver

        resolver = AttributeResolver()

        # Test with nested path
        result = resolver.resolve(
            instrument=self.instrument,
            dotted_path="collection_request.id",
        )

        self.assertIn("data", result)
        self.assertEqual(result["data"], self.cr.id)

    def test_debug_resolver(self):
        """Test DebugResolver pattern matching."""
        from ..collection.resolvers import DebugResolver

        resolver = DebugResolver()
        result = resolver.apply("debug:{'data': [1, 2, 3]}")

        self.assertIsNotNone(result)
        self.assertIn("expression", result)

    def test_debug_resolver_resolve(self):
        """Test DebugResolver.resolve evaluates expression."""
        from ..collection.resolvers import DebugResolver

        resolver = DebugResolver()
        result = resolver.resolve(
            instrument=self.instrument,
            expression="{'data': [1, 2, 3]}",
        )

        self.assertEqual(result["data"], [1, 2, 3])

    def test_resolver_full_pattern(self):
        """Test Resolver.full_pattern property."""
        from ..collection.resolvers import InstrumentResolver

        resolver = InstrumentResolver()
        pattern = resolver.full_pattern

        self.assertIn("^instrument:", pattern)
        self.assertTrue(pattern.endswith("$"))

    def test_register_function(self):
        """Test register function adds to registry."""
        from ..collection import resolvers

        # Verify registry exists and contains registered resolvers
        self.assertIsInstance(resolvers.registry, list)
        self.assertGreater(len(resolvers.registry), 0)


class RegistryTests(TestCase):
    """Tests for django_input_collection/schema/registry.py"""

    def test_condition_resolver_registry_register(self):
        """Test ConditionResolverRegistry.register method."""
        from ..schema.registry import ConditionResolverRegistry

        def custom_resolver(source, values):
            return f"custom:{source}"

        ConditionResolverRegistry.register("test_type", custom_resolver, "import")

        # Verify it's registered
        result = ConditionResolverRegistry.resolve_import("test_type", "test-source")
        self.assertEqual(result, "custom:test-source")

        # Clean up
        del ConditionResolverRegistry._import_resolvers["test_type"]

    def test_condition_resolver_registry_register_export(self):
        """Test ConditionResolverRegistry.register for export direction."""
        from ..schema.registry import ConditionResolverRegistry

        def custom_exporter(path):
            return path.replace("-", "_")

        ConditionResolverRegistry.register("test_export", custom_exporter, "export")

        result = ConditionResolverRegistry.resolve_export("test_export", "test-path")
        self.assertEqual(result, "test_path")

        # Clean up
        del ConditionResolverRegistry._export_resolvers["test_export"]

    def test_condition_resolver_registry_invalid_direction(self):
        """Test ConditionResolverRegistry.register with invalid direction."""
        from ..schema.registry import ConditionResolverRegistry

        with self.assertRaises(ValueError):
            ConditionResolverRegistry.register("type", lambda x, y: x, "invalid")

    def test_condition_resolver_registry_resolve_import_instrument(self):
        """Test ConditionResolverRegistry.resolve_import for instrument type."""
        from ..schema.registry import ConditionResolverRegistry

        result = ConditionResolverRegistry.resolve_import("instrument", "measure-id")
        self.assertEqual(result, "instrument:measure-id")

    def test_condition_resolver_registry_resolve_import_unknown(self):
        """Test ConditionResolverRegistry.resolve_import for unknown type."""
        from ..schema.registry import ConditionResolverRegistry

        result = ConditionResolverRegistry.resolve_import("unknown_type", "source")
        self.assertIsNone(result)

    def test_condition_resolver_registry_resolve_export_unregistered(self):
        """Test ConditionResolverRegistry.resolve_export for unregistered type."""
        from ..schema.registry import ConditionResolverRegistry

        result = ConditionResolverRegistry.resolve_export("unregistered", "path")
        self.assertIsNone(result)

    def test_condition_resolver_registry_get_registered_types(self):
        """Test ConditionResolverRegistry.get_registered_types."""
        from ..schema.registry import ConditionResolverRegistry

        types = ConditionResolverRegistry.get_registered_types()
        self.assertIn("instrument", types)

    def test_bound_response_registry_create_no_handler(self):
        """Test BoundResponseRegistry.create with no handler."""
        from ..schema.registry import BoundResponseRegistry

        # Save original handler
        original_handler = BoundResponseRegistry._handler
        BoundResponseRegistry._handler = None

        try:
            instrument = factories.CollectionInstrumentFactory.create()
            response = factories.SuggestedResponseFactory.create(data="TestResponse")

            BoundResponseRegistry.create(instrument, response, {})

            # Should add to suggested_responses
            self.assertIn(response, instrument.suggested_responses.all())
        finally:
            BoundResponseRegistry._handler = original_handler

    def test_bound_response_registry_create_with_handler(self):
        """Test BoundResponseRegistry.create with custom handler."""
        from ..schema.registry import BoundResponseRegistry

        original_handler = BoundResponseRegistry._handler

        mock_handler = Mock()
        mock_handler.create = Mock()
        BoundResponseRegistry._handler = mock_handler

        try:
            instrument = factories.CollectionInstrumentFactory.create()
            response = factories.SuggestedResponseFactory.create(data="TestResponse2")

            BoundResponseRegistry.create(instrument, response, {"flag": True})

            mock_handler.create.assert_called_once_with(instrument, response, {"flag": True})
        finally:
            BoundResponseRegistry._handler = original_handler

    def test_bound_response_registry_export_no_handler(self):
        """Test BoundResponseRegistry.export with no handler."""
        from ..schema.registry import BoundResponseRegistry

        original_handler = BoundResponseRegistry._handler
        BoundResponseRegistry._handler = None

        try:
            instrument = factories.CollectionInstrumentFactory.create()
            result = BoundResponseRegistry.export(instrument)
            self.assertEqual(result, {})
        finally:
            BoundResponseRegistry._handler = original_handler

    def test_bound_response_registry_export_with_handler(self):
        """Test BoundResponseRegistry.export with custom handler."""
        from ..schema.registry import BoundResponseRegistry

        original_handler = BoundResponseRegistry._handler

        mock_handler = Mock()
        mock_handler.export = Mock(return_value={"flag": True})
        BoundResponseRegistry._handler = mock_handler

        try:
            instrument = factories.CollectionInstrumentFactory.create()
            result = BoundResponseRegistry.export(instrument)

            mock_handler.export.assert_called_once_with(instrument)
            self.assertEqual(result, {"flag": True})
        finally:
            BoundResponseRegistry._handler = original_handler

    def test_bound_response_registry_has_handler(self):
        """Test BoundResponseRegistry.has_handler method."""
        from ..schema.registry import BoundResponseRegistry

        original_handler = BoundResponseRegistry._handler

        BoundResponseRegistry._handler = None
        self.assertFalse(BoundResponseRegistry.has_handler())

        BoundResponseRegistry._handler = Mock()
        self.assertTrue(BoundResponseRegistry.has_handler())

        BoundResponseRegistry._handler = original_handler

    def test_register_condition_resolver_decorator(self):
        """Test register_condition_resolver decorator."""
        from ..schema.registry import (
            register_condition_resolver,
            ConditionResolverRegistry,
        )

        @register_condition_resolver("decorator_test")
        def test_resolver(source, values):
            return f"decorated:{source}"

        result = ConditionResolverRegistry.resolve_import("decorator_test", "src")
        self.assertEqual(result, "decorated:src")

        # Clean up
        del ConditionResolverRegistry._import_resolvers["decorator_test"]

    def test_register_bound_response_handler_decorator(self):
        """Test register_bound_response_handler decorator."""
        from ..schema.registry import (
            register_bound_response_handler,
            BoundResponseRegistry,
        )

        original_handler = BoundResponseRegistry._handler

        @register_bound_response_handler()
        class TestHandler:
            @staticmethod
            def create(instrument, response, flags):
                pass

            @staticmethod
            def export(instrument):
                return {}

        self.assertTrue(BoundResponseRegistry.has_handler())

        BoundResponseRegistry._handler = original_handler


class MatcherTests(TestCase):
    """Tests for django_input_collection/collection/matchers.py"""

    def test_list_wrap_string(self):
        """Test list_wrap with string."""
        from ..collection.matchers import list_wrap

        result = list_wrap("test")
        self.assertEqual(result, ["test"])

    def test_list_wrap_string_no_wrap(self):
        """Test list_wrap with wrap_strings=False."""
        from ..collection.matchers import list_wrap

        result = list_wrap("test", wrap_strings=False)
        self.assertEqual(result, "test")

    def test_list_wrap_list(self):
        """Test list_wrap with list."""
        from ..collection.matchers import list_wrap

        result = list_wrap([1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    def test_list_wrap_mapping(self):
        """Test list_wrap with dict."""
        from ..collection.matchers import list_wrap

        result = list_wrap({"key": "value"})
        self.assertEqual(result, [{"key": "value"}])

    def test_list_wrap_coerce_iterables(self):
        """Test list_wrap with coerce_iterables=True."""
        from ..collection.matchers import list_wrap

        result = list_wrap((1, 2, 3), coerce_iterables=True)
        self.assertEqual(result, [1, 2, 3])

    def test_eval_sample_valid(self):
        """Test eval_sample with valid expression."""
        from ..collection.matchers import eval_sample

        result = eval_sample("[1, 2, 3]")
        self.assertEqual(result, [1, 2, 3])

    def test_eval_sample_invalid(self):
        """Test eval_sample with invalid expression."""
        from ..collection.matchers import eval_sample

        result = eval_sample("not valid python")
        self.assertEqual(result, "not valid python")

    def test_coerce_type_same_type(self):
        """Test coerce_type when types match."""
        from ..collection.matchers import coerce_type

        result = coerce_type("123", "hello")
        self.assertEqual(result, "123")

    def test_coerce_type_int_to_str(self):
        """Test coerce_type converting int to str."""
        from ..collection.matchers import coerce_type

        result = coerce_type("123", 456)
        self.assertEqual(result, 123)

    def test_matcher_any(self):
        """Test any matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["value"], "any")
        self.assertTrue(result)

        result = test_condition_case([], "any")
        self.assertFalse(result)

    def test_matcher_none(self):
        """Test none matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case([], "none")
        self.assertTrue(result)

        result = test_condition_case(["value"], "none")
        self.assertFalse(result)

    def test_matcher_all_suggested(self):
        """Test all_suggested matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["Yes"], "all-suggested", suggested_values=["Yes", "No"])
        self.assertTrue(result)

        result = test_condition_case(["Custom"], "all-suggested", suggested_values=["Yes", "No"])
        self.assertFalse(result)

    def test_matcher_one_suggested(self):
        """Test one_suggested matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(
            ["Yes", "Custom"], "one-suggested", suggested_values=["Yes", "No"]
        )
        self.assertTrue(result)

        result = test_condition_case(
            ["Custom1", "Custom2"], "one-suggested", suggested_values=["Yes", "No"]
        )
        self.assertFalse(result)

    def test_matcher_all_custom(self):
        """Test all_custom matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(
            ["Custom1", "Custom2"], "all-custom", suggested_values=["Yes", "No"]
        )
        self.assertTrue(result)

        result = test_condition_case(
            ["Yes", "Custom"], "all-custom", suggested_values=["Yes", "No"]
        )
        self.assertFalse(result)

    def test_matcher_one_custom(self):
        """Test one_custom matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(
            ["Yes", "Custom"], "one-custom", suggested_values=["Yes", "No"]
        )
        self.assertTrue(result)

        result = test_condition_case(["Yes", "No"], "one-custom", suggested_values=["Yes", "No"])
        self.assertFalse(result)

    def test_matcher_match(self):
        """Test match matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["Yes"], "match", match_data="Yes")
        self.assertTrue(result)

        result = test_condition_case(["No"], "match", match_data="Yes")
        self.assertFalse(result)

    def test_matcher_mismatch(self):
        """Test mismatch matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["No"], "mismatch", match_data="Yes")
        self.assertTrue(result)

        result = test_condition_case(["Yes"], "mismatch", match_data="Yes")
        self.assertFalse(result)

    def test_matcher_greater_than(self):
        """Test greater_than matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case([10], "greater_than", match_data="5")
        self.assertTrue(result)

        result = test_condition_case([3], "greater_than", match_data="5")
        self.assertFalse(result)

    def test_matcher_less_than(self):
        """Test less_than matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case([3], "less_than", match_data="5")
        self.assertTrue(result)

        result = test_condition_case([10], "less_than", match_data="5")
        self.assertFalse(result)

    def test_matcher_contains(self):
        """Test contains matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["hello world"], "contains", match_data="world")
        self.assertTrue(result)

        result = test_condition_case(["hello"], "contains", match_data="world")
        self.assertFalse(result)

    def test_matcher_not_contains(self):
        """Test not_contains matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["hello"], "not-contains", match_data="world")
        self.assertTrue(result)

        result = test_condition_case(["hello world"], "not-contains", match_data="world")
        self.assertFalse(result)

    def test_matcher_one(self):
        """Test one matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["a"], "one", match_data="['a', 'b', 'c']")
        self.assertTrue(result)

        result = test_condition_case(["x"], "one", match_data="['a', 'b', 'c']")
        self.assertFalse(result)

    def test_matcher_zero(self):
        """Test zero matcher."""
        from ..collection.matchers import test_condition_case

        result = test_condition_case(["x"], "zero", match_data="['a', 'b', 'c']")
        self.assertTrue(result)

        result = test_condition_case(["a"], "zero", match_data="['a', 'b', 'c']")
        self.assertFalse(result)

    def test_resolve_matcher(self):
        """Test resolve_matcher function."""
        from ..collection.matchers import resolve_matcher, matchers

        matcher = resolve_matcher("all-suggested")
        self.assertEqual(matcher, matchers.all_suggested)

    def test_test_condition_case_with_key_functions(self):
        """Test test_condition_case with key_input and key_case."""
        from ..collection.matchers import test_condition_case

        # Test with key functions that convert to lowercase
        result = test_condition_case(
            ["YES"],
            "match",
            match_data="yes",
            key_input=str.lower,
            key_case=str.lower,
        )
        self.assertTrue(result)


class InputMethodBaseTests(TestCase):
    """Tests for django_input_collection/collection/methods/base.py"""

    def test_input_method_init(self):
        """Test InputMethod initialization."""
        from ..collection.methods.base import InputMethod

        method = InputMethod()
        self.assertIsNotNone(method.errors)

    def test_input_method_init_with_kwargs(self):
        """Test InputMethod initialization with kwargs."""
        from ..collection.methods.base import InputMethod

        method = InputMethod(data_type="string")
        self.assertEqual(method.data_type, "string")

    def test_input_method_update(self):
        """Test InputMethod.update method."""
        from ..collection.methods.base import InputMethod

        method = InputMethod()
        method.update(data_type="integer")
        self.assertEqual(method.data_type, "integer")

    def test_input_method_update_invalid_key(self):
        """Test InputMethod.update with invalid key raises error."""
        from ..collection.methods.base import InputMethod

        method = InputMethod()
        with self.assertRaises(AttributeError):
            method.update(_invalid_key="value")

    def test_input_method_data_property(self):
        """Test InputMethod.data property."""
        from ..collection.methods.base import InputMethod

        method = InputMethod(data_type="string")
        data = method.data

        self.assertIsInstance(data, dict)
        self.assertNotIn("cleaner", data)
        self.assertNotIn("errors", data)
        self.assertIn("data_type", data)

    def test_input_method_serialize(self):
        """Test InputMethod.serialize method."""
        from ..collection.methods.base import InputMethod

        method = InputMethod(data_type="string")
        serialized = method.serialize()

        self.assertIn("meta", serialized)
        self.assertIn("method_class", serialized["meta"])
        self.assertIn("data_type", serialized["meta"])
        self.assertIn("constraints", serialized)

    def test_input_method_get_constraints(self):
        """Test InputMethod.get_constraints method."""
        from ..collection.methods.base import InputMethod

        method = InputMethod()
        constraints = method.get_constraints()
        self.assertEqual(constraints, {})

    def test_input_method_get_data_display(self):
        """Test InputMethod.get_data_display method."""
        from ..collection.methods.base import InputMethod

        method = InputMethod()
        display = method.get_data_display(123)
        self.assertEqual(display, "123")

    def test_input_method_clean_input(self):
        """Test InputMethod.clean_input method."""
        from ..collection.methods.base import InputMethod

        method = InputMethod()
        result = method.clean_input("test")
        self.assertEqual(result, "test")

    def test_input_method_clean_input_with_cleaner(self):
        """Test InputMethod.clean_input with custom cleaner."""
        from ..collection.methods.base import InputMethod

        method = InputMethod(cleaner=lambda x: x.upper())
        result = method.clean_input("test")
        self.assertEqual(result, "TEST")

    def test_input_method_clean_input_passes_data(self):
        """Test InputMethod.clean_input passes data through cleaner."""
        from ..collection.methods.base import InputMethod

        result_holder = {}

        def track_cleaner(data):
            result_holder["data"] = data
            return data.upper()

        method = InputMethod(cleaner=track_cleaner)
        result = method.clean_input("hello")

        self.assertEqual(result, "HELLO")
        self.assertEqual(result_holder["data"], "hello")

    def test_input_method_get_error(self):
        """Test InputMethod.get_error method."""
        from ..collection.methods.base import InputMethod

        method = InputMethod()
        # Use Exception class as the code, which exists in base_errors
        error = method.get_error(Exception, exception="test error")
        self.assertIn("test error", str(error))

    def test_filter_safe_dict(self):
        """Test filter_safe_dict function."""
        from ..collection.methods.base import filter_safe_dict

        data = {
            "valid_key": "value",
            "_private": "hidden",
            "other": 123,
        }

        result = filter_safe_dict(data)
        self.assertIn("valid_key", result)
        self.assertNotIn("_private", result)

    def test_filter_safe_dict_with_attrs(self):
        """Test filter_safe_dict with attrs filter."""
        from ..collection.methods.base import filter_safe_dict

        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        result = filter_safe_dict(data, attrs=["key1", "key2"])
        self.assertIn("key1", result)
        self.assertIn("key2", result)
        self.assertNotIn("key3", result)

    def test_filter_safe_dict_with_exclude(self):
        """Test filter_safe_dict with exclude filter."""
        from ..collection.methods.base import filter_safe_dict

        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        result = filter_safe_dict(data, exclude=["key2"])
        self.assertIn("key1", result)
        self.assertNotIn("key2", result)
        self.assertIn("key3", result)

    def test_flatten_dicts(self):
        """Test flatten_dicts function."""
        from ..collection.methods.base import flatten_dicts

        result = flatten_dicts({"a": 1}, {"b": 2}, c=3)
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3})


class FormMethodTests(TestCase):
    """Tests for django_input_collection/collection/methods/form.py"""

    def test_form_field_method_get_formfield(self):
        """Test FormFieldMethod.get_formfield method."""
        from ..collection.methods.form import FormFieldMethod
        from django import forms

        method = FormFieldMethod(formfield=forms.CharField)
        field = method.get_formfield()
        self.assertIsInstance(field, forms.CharField)

    def test_form_field_method_get_formfield_instance(self):
        """Test FormFieldMethod.get_formfield with instance."""
        from ..collection.methods.form import FormFieldMethod
        from django import forms

        char_field = forms.CharField(max_length=100)
        method = FormFieldMethod(formfield=char_field)
        field = method.get_formfield()
        self.assertEqual(field, char_field)

    def test_form_field_method_copy_attrs(self):
        """Test FormFieldMethod.copy_attrs method."""
        from ..collection.methods.form import FormFieldMethod
        from django import forms

        method = FormFieldMethod(formfield=forms.CharField, label="Test Label")

        target = Mock()
        method.copy_attrs(target, "label", help_text="Custom Help")

        self.assertEqual(target.label, "Test Label")
        self.assertEqual(target.help_text, "Custom Help")

    def test_form_field_method_clean(self):
        """Test FormFieldMethod.clean method."""
        from ..collection.methods.form import FormFieldMethod
        from django import forms

        method = FormFieldMethod(formfield=forms.IntegerField())
        result = method.clean("123")
        self.assertEqual(result, 123)

    def test_form_method_get_form(self):
        """Test FormMethod.get_form method."""
        from ..collection.methods.form import FormMethod
        from django import forms

        class TestForm(forms.Form):
            name = forms.CharField()

        method = FormMethod(form_class=TestForm)
        form = method.get_form()
        self.assertIsInstance(form, TestForm)


class ConditionsModelTests(TestCase):
    """Additional tests for django_input_collection/models/conditions.py"""

    def test_condition_str(self):
        """Test Condition string representation."""
        cr = factories.CollectionRequestFactory.create()
        instrument = factories.CollectionInstrumentFactory.create(collection_request=cr)
        condition_group = factories.ConditionGroupFactory.create()
        condition = factories.ConditionFactory.create(
            instrument=instrument,
            data_getter="instrument:test",
            condition_group=condition_group,
        )

        result = str(condition)
        self.assertIn("depends on", result)
        self.assertIn("instrument", result)

    def test_condition_group_str_unsaved(self):
        """Test ConditionGroup string representation when unsaved."""
        from ..models.conditions import ConditionGroup

        group = ConditionGroup()
        result = str(group)
        self.assertEqual(result, "(Unsaved)")

    def test_condition_group_str_empty(self):
        """Test ConditionGroup string representation when empty."""
        from ..models.conditions import ConditionGroup

        group = ConditionGroup.objects.create(nickname=None)
        result = str(group)
        self.assertEqual(result, "(Empty)")

    def test_condition_group_test_all_pass(self):
        """Test ConditionGroup.test with all-pass requirement."""
        group = factories.ConditionGroupFactory.create(requirement_type="all-pass")
        case1 = factories.CaseFactory.create(match_type="any")
        group.cases.add(case1)

        result = group.test(data=["value"])
        self.assertTrue(result)

    def test_condition_group_test_one_pass(self):
        """Test ConditionGroup.test with one-pass requirement."""
        group = factories.ConditionGroupFactory.create(requirement_type="one-pass")
        case1 = factories.CaseFactory.create(match_type="none")
        case2 = factories.CaseFactory.create(match_type="any")
        group.cases.add(case1, case2)

        result = group.test(data=["value"])
        self.assertTrue(result)

    def test_condition_group_test_all_fail(self):
        """Test ConditionGroup.test with all-fail requirement."""
        group = factories.ConditionGroupFactory.create(requirement_type="all-fail")
        case1 = factories.CaseFactory.create(match_type="none")
        group.cases.add(case1)

        result = group.test(data=[])
        self.assertFalse(result)

    def test_case_str(self):
        """Test Case string representation."""
        case = factories.CaseFactory.create(match_type="any")
        result = str(case)
        self.assertIsNotNone(result)

    def test_case_describe(self):
        """Test Case.describe method."""
        case = factories.CaseFactory.create(match_type="match", match_data="test")
        result = case.describe()
        self.assertIn(b"test", result)

    def test_case_describe_unsaved(self):
        """Test Case.describe when unsaved."""
        from ..models.conditions import Case

        case = Case(match_type="any")
        result = case.describe()
        self.assertEqual(result, "(Unsaved)")

    def test_case_test(self):
        """Test Case.test method."""
        case = factories.CaseFactory.create(match_type="any")
        result = case.test(data=["value"])
        self.assertTrue(result)

    def test_case_get_flags(self):
        """Test Case.get_flags method."""
        case = factories.CaseFactory.create(match_type="match", match_data="test")
        flags = case.get_flags()
        self.assertEqual(flags["match_type"], "match")
        self.assertEqual(flags["match_data"], "test")


class CollectionInstrumentTests(TestCase):
    """Additional tests for CollectionInstrument model."""

    def test_instrument_test_conditions_all_pass(self):
        """Test CollectionInstrument.test_conditions with all-pass."""
        cr = factories.CollectionRequestFactory.create()
        instrument = factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            test_requirement_type="all-pass",
        )

        # No conditions should return True
        result = instrument.test_conditions()
        self.assertTrue(result)

    def test_instrument_get_choices(self):
        """Test CollectionInstrument.get_choices method."""
        cr = factories.CollectionRequestFactory.create()
        response1 = factories.SuggestedResponseFactory.create(data="Yes")
        response2 = factories.SuggestedResponseFactory.create(data="No")
        instrument = factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            suggested_responses=[response1, response2],
        )

        choices = instrument.get_choices()
        self.assertIn("Yes", choices)
        self.assertIn("No", choices)

    def test_instrument_get_child_instruments(self):
        """Test CollectionInstrument.get_child_instruments method."""
        cr = factories.CollectionRequestFactory.create()
        parent = factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="parent-measure",
        )
        child = factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="child-measure",
        )

        # Create condition linking child to parent
        condition_group = factories.ConditionGroupFactory.create()
        factories.ConditionFactory.create(
            instrument=child,
            data_getter=f"instrument:{parent.pk}",
            condition_group=condition_group,
        )

        children = parent.get_child_instruments()
        self.assertIn(child, children)


class ManagerTests(TestCase):
    """Tests for django_input_collection/managers/"""

    def test_collection_instrument_queryset(self):
        """Test CollectionInstrument manager/queryset."""
        from ..managers import CollectionInstrumentQuerySet

        cr = factories.CollectionRequestFactory.create()
        factories.CollectionInstrumentFactory.create(collection_request=cr)

        from ..models import CollectionInstrument

        qs = CollectionInstrument.objects.all()
        self.assertIsInstance(qs, CollectionInstrumentQuerySet)

    def test_collected_input_queryset(self):
        """Test CollectedInput manager/queryset."""
        from ..managers import CollectedInputQuerySet

        from ..models import CollectedInput

        qs = CollectedInput.objects.all()
        self.assertIsInstance(qs, CollectedInputQuerySet)


class CollectionUtilsTests(TestCase):
    """Tests for django_input_collection/collection/utils.py"""

    def test_collection_utils_imports(self):
        """Test that collection utils can be imported."""
        from ..collection import utils

        self.assertIsNotNone(utils)


class SchemaExporterAdditionalTests(TestCase):
    """Additional tests for schema exporter edge cases."""

    def test_export_instrument_without_group(self):
        """Test exporting instrument without a group."""
        from ..schema.exporter import CollectionRequestExporter

        cr = factories.CollectionRequestFactory.create()
        factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="ungrouped-q",
            text="Ungrouped Question",
            group=None,
        )

        exporter = CollectionRequestExporter()
        schema = exporter.export(cr)

        # Should have an "Ungrouped" or default section
        self.assertEqual(len(schema["sections"]), 1)
        self.assertEqual(len(schema["sections"][0]["questions"]), 1)

    def test_export_with_conditions(self):
        """Test exporting schema with conditions."""
        from ..schema.exporter import CollectionRequestExporter

        cr = factories.CollectionRequestFactory.create()
        group = factories.CollectionGroupFactory.create(id="test-section")

        factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="parent-q",
            group=group,
            order=10,
        )
        child = factories.CollectionInstrumentFactory.create(
            collection_request=cr,
            measure__id="child-q",
            group=group,
            order=20,
        )

        # Create condition
        condition_group = factories.ConditionGroupFactory.create()
        case = factories.CaseFactory.create(match_type="match", match_data="Yes")
        condition_group.cases.add(case)
        factories.ConditionFactory.create(
            instrument=child,
            data_getter="instrument:parent-q",
            condition_group=condition_group,
        )

        exporter = CollectionRequestExporter()
        schema = exporter.export(cr)

        child_q = None
        for section in schema["sections"]:
            for q in section["questions"]:
                if q["measure_id"] == "child-q":
                    child_q = q
                    break

        self.assertIsNotNone(child_q)
        self.assertIn("conditions", child_q)


class SchemaBuilderAdditionalTests(TestCase):
    """Additional tests for schema builder edge cases."""

    def test_build_with_group_conditions(self):
        """Test building schema with group (AND/OR) conditions."""
        from ..schema.builder import CollectionRequestBuilder

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
                            "type": "multiple-choice",
                            "responses": ["Yes", "No"],
                        },
                        {
                            "measure_id": "q2",
                            "text": "Question 2",
                            "type": "multiple-choice",
                            "responses": ["A", "B"],
                        },
                        {
                            "measure_id": "q3",
                            "text": "Question 3",
                            "type": "open",
                            "conditions": [
                                {
                                    "logic": "all",
                                    "rules": [
                                        {
                                            "type": "instrument",
                                            "source": "q1",
                                            "match_type": "match",
                                            "values": ["Yes"],
                                        },
                                        {
                                            "type": "instrument",
                                            "source": "q2",
                                            "match_type": "match",
                                            "values": ["A"],
                                        },
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema)

        q3 = cr.collectioninstrument_set.get(measure_id="q3")
        self.assertEqual(q3.conditions.count(), 2)

    def test_build_with_constraints(self):
        """Test building schema with numeric constraints."""
        from ..schema.builder import CollectionRequestBuilder

        schema = {
            "version": "1.0",
            "name": "Test Checklist",
            "sections": [
                {
                    "name": "Section 1",
                    "questions": [
                        {
                            "measure_id": "q1",
                            "text": "Enter a number",
                            "type": "integer",
                            "constraints": {"min": 0, "max": 100},
                        }
                    ],
                }
            ],
        }

        builder = CollectionRequestBuilder()
        cr = builder.build(schema)

        q1 = cr.collectioninstrument_set.get(measure_id="q1")
        self.assertIsNotNone(q1)
        self.assertEqual(q1.type.id, "integer")
