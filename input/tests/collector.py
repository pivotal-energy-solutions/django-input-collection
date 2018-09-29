from inspect import isclass

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ..collection import collectors, InputMethod
from ..models import get_input_model
from . import factories


User = get_user_model()
CollectedInput = get_input_model()
Collector = collectors.Collector


class CollectorRegistrationTests(TestCase):
    def test_basescollectors_are_unregistered(self):
        """ Verifies that the base API collector subclass is NOT directly usable. """
        self.assertEqual(hasattr(collectors.BaseCollector, '__noregister__'), True)
        self.assertEqual(collectors.BaseCollector.__noregister__, True)
        self.assertNotIn(collectors.BaseCollector, collectors.registry)

        self.assertEqual(hasattr(collectors.BaseAPICollector, '__noregister__'), True)
        self.assertEqual(collectors.BaseAPICollector.__noregister__, True)
        self.assertNotIn(collectors.BaseAPICollector, collectors.registry)

    def test_basecollectors_cannot_be_inspected_for_registration_identifier(self):
        """ Verifies that the base API collector subclass is NOT directly usable. """
        with self.assertRaises(collectors.CollectorException):
            collectors.BaseCollector.get_identifier()

        with self.assertRaises(collectors.CollectorException):
            collectors.BaseAPICollector.get_identifier()

    def test_basecollectors_cannot_be_registered(self):
        """ Verifies that the base API collector subclass is NOT directly usable. """
        with self.assertRaises(collectors.CollectorException):
            collectors.BaseCollector.register()

        with self.assertRaises(collectors.CollectorException):
            collectors.BaseAPICollector.get_identifier()

    def test_collector_is_registered_by_default(self):
        """ Verifies that the base Collector is usable out of the box. """
        self.assertIn(Collector.get_identifier(), collectors.registry)
        self.assertEqual(collectors.registry[Collector.get_identifier()], Collector)


class FooMethod(InputMethod):
    foo1 = None
    foo2 = None


class BarMethod(InputMethod):
    bar1 = None
    bar2 = None


class InputMethodTests(TestCase):
    def test_init_merges_dict_with_kwargs(self):
        self.assertEqual(FooMethod({'foo1': 'foo1'}, foo2='foo2').data, {'foo1': 'foo1', 'foo2': 'foo2'})

    def test_update_merges_dict_with_kwargs(self):
        method = FooMethod()

        def with_update(d, **kwargs):
            method.update(d, **kwargs)
            return method.data
            
        self.assertEqual(with_update({'foo1': 'foo1'}, foo2='foo2'), {'foo1': 'foo1', 'foo2': 'foo2'})

    def test_init_sets_userdict_data_to_defaults(self):
        self.assertEqual(FooMethod().data, {'foo1': None, 'foo2': None})

        class CustomFooMethod(FooMethod):  # Something we can monkeypatch without consequences
            pass
        CustomFooMethod.bar = None

        self.assertEqual(CustomFooMethod().data, {'foo1': None, 'foo2': None, 'bar': None})

    def test_init_kwarg_updates_userdict_data(self):
        self.assertEqual(FooMethod(foo1='foo1').data, {'foo1': 'foo1', 'foo2': None})

    def test_init_kwarg_updates_attribute(self):
        self.assertEqual(FooMethod(foo1='foo1').foo1, 'foo1')

    def test_init_kwarg_not_matching_existing_attributes_raises_error(self):
        with self.assertRaises(AttributeError):
            FooMethod(bar='bar')

        class CustomFooMethod(FooMethod):  # Something we can monkeypatch without consequences
            pass

        with self.assertRaises(AttributeError):
            CustomFooMethod(bar='bar')
        CustomFooMethod.bar = None
        self.assertEqual(CustomFooMethod(bar='bar').data, {'foo1': None, 'foo2': None, 'bar': 'bar'})

    def test_update_modifies_attributes(self):
        method = FooMethod()
        method.update({'foo1': 'foo1'})
        self.assertEqual(method.foo1, 'foo1')

    def test_update_modifies_userdict_data(self):
        method = FooMethod()
        method.update({'foo1': 'foo1'})
        self.assertIn('foo1', method.data)
        self.assertEqual(method.data['foo1'], 'foo1')
        self.assertEqual(method.data, {'foo1': 'foo1', 'foo2': None})

    def test_init_silencer_raises_no_error(self):
        try:
            FooMethod(bar='bar', _raise=False)
        except AttributeError as e:
            self.fail("Silencer did not stop AttributeError: %s" % (e,))

    def test_update_silencer_raises_no_error(self):
        try:
            FooMethod(bar='bar', _raise=False)
        except AttributeError as e:
            self.fail("Silencer did not stop AttributeError: %s" % (e,))


class CollectorStaticTests(TestCase):
    def setUp(self):
        self.collection_request = factories.CollectionRequestFactory.create()
        self.collector = Collector(self.collection_request)

    def with_methods(self, instrument, instrument_measure, instrument_type, measure, type):
        instrument.measure_id = instrument_measure
        instrument.type_id = instrument_type
        self.collector.measure_methods = measure
        self.collector.type_methods = type
        return self.collector.get_method(instrument)

    def with_measuremethods(self, instrument, instrument_measure, methods):
        return self.with_methods(instrument, instrument_measure, None, measure=methods, type={})

    def with_typemethods(self, instrument, instrument_type, methods):
        return self.with_methods(instrument, 'dummy', instrument_type, measure={}, type=methods)

    def test_get_type_methods_retrieves_class_attribute_or_empty_dict(self):
        self.assertEqual(Collector.type_methods, None)
        self.assertEqual(self.collector.get_type_methods(), {})

        self.collector.type_methods = {'foo': 'bar'}
        self.assertEqual(self.collector.get_type_methods(), {'foo': 'bar'})

    def test_get_measure_methods_retrieves_class_attribute_or_empty_dict(self):
        self.assertEqual(Collector.measure_methods, None)
        self.assertEqual(self.collector.get_measure_methods(), {})

        self.collector.measure_methods = {'foo': 'bar'}
        self.assertEqual(self.collector.get_measure_methods(), {'foo': 'bar'})

    def test_get_method_returns_default_inputmethod_instance(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })
        method = self.with_methods(i, 'foo', None, measure={}, type={})

        self.assertEqual(isclass(method), False)
        self.assertEqual(method.__class__, InputMethod)

    def test_get_method_instantiates_class_reference(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        def with_measuremethods(instrument_measure, methods):
            return self.with_methods(i, instrument_measure, measure=methods, type={})

        self.assertEqual(isclass(self.with_measuremethods(i, 'a', {'a': FooMethod})), False)
        self.assertEqual(self.with_measuremethods(i, 'a', {'a': FooMethod}).__class__, FooMethod)

    def test_get_method_keeps_direct_instance_reference(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        foo = FooMethod()
        self.assertEqual(isclass(self.with_measuremethods(i, 'a', {'a': foo})), False)
        self.assertEqual(self.with_measuremethods(i, 'a', {'a': foo}), foo)

    def test_get_method_retrieves_override_from_measure_methods(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        default = InputMethod()
        foo = FooMethod()

        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={}), default)
        self.assertEqual(self.with_methods(i, 'a', None, measure={'a': foo}, type={}), foo)
        self.assertEqual(self.with_methods(i, 'a', 'special', measure={}, type={}), default)
        self.assertEqual(self.with_methods(i, 'a', 'special', measure={'a': foo}, type={}), foo)
        self.assertEqual(self.with_methods(i, 'b', 'special', measure={'a': foo}, type={}), default)
        self.assertEqual(self.with_methods(i, 'c', 'special', measure={'a': foo}, type={}), default)

    def test_get_method_retrieves_override_from_type_methods(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        default = InputMethod()
        foo = FooMethod()

        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={}), default)
        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={None: foo}), foo)
        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={}), default)
        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={None: foo}), foo)
        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={'special': foo}), default)
        self.assertEqual(self.with_methods(i, 'a', 'special', measure={}, type={'special': foo}), foo)
        self.assertEqual(self.with_methods(i, 'a', 'special', measure={}, type={None: foo}), default)
        self.assertEqual(self.with_methods(i, 'b', 'special', measure={}, type={'special': foo}), foo)
        self.assertEqual(self.with_methods(i, 'c', 'special', measure={}, type={'special': foo}), foo)

    def test_get_method_retrieves_measure_methods_before_type_methods(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        default = InputMethod()
        foo = FooMethod()
        bar = BarMethod()

        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={}), default)
        self.assertEqual(self.with_methods(i, 'a', None, measure={}, type={None: bar}), bar)
        self.assertEqual(self.with_methods(i, 'a', None, measure={'a': foo}, type={}), foo)
        self.assertEqual(self.with_methods(i, 'a', None, measure={'a': foo}, type={None: bar}), foo)
        self.assertEqual(self.with_methods(i, 'a', None, measure={'b': foo}, type={'special': bar}), default)
        self.assertEqual(self.with_methods(i, 'a', 'special', measure={'b': foo}, type={'special': bar}), bar)
        self.assertEqual(self.with_methods(i, 'a', 'special', measure={'b': foo}, type={None: bar}), default)
        self.assertEqual(self.with_methods(i, 'b', 'special', measure={'b': foo}, type={'special': bar}), foo)
        self.assertEqual(self.with_methods(i, 'c', 'special', measure={'b': foo}, type={'special': bar}), bar)

    def test_get_method_adds_get_method_kwargs_to_existing_instance(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        foo = FooMethod(foo1='foo1')

        def with_methodkwargs(kwargs):
            self.collector.get_method_kwargs = lambda *a, **kw: kwargs
            return self.collector.get_method(i)

        method = self.with_measuremethods(i, 'a', {'a': foo})
        self.assertEqual(with_methodkwargs({'foo2': 'foo2'}).data, {'foo1': 'foo1', 'foo2': 'foo2'})

    def test_get_method_raises_error_for_unrecognized_get_method_kwargs(self):
        i = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        class CustomFooMethod(FooMethod):  # Something we can monkeypatch without consequences
            pass

        foo = CustomFooMethod(foo1='foo1')

        def with_methodkwargs(kwargs):
            self.collector.get_method_kwargs = lambda *a, **kw: kwargs
            return self.collector.get_method(i)

        method = self.with_measuremethods(i, 'a', {'a': foo})
        with self.assertRaises(AttributeError):
            with_methodkwargs({'bar': 'bar'})

        # Now prove the AttributeError isn't a fluke
        foo.bar = None
        self.assertEqual(with_methodkwargs({'bar': 'bar'}).data, {'foo1': 'foo1', 'foo2': None, 'bar': 'bar'})


class CollectorRuntimeTests(TestCase):
    def setUp(self):
        self.collection_request = factories.CollectionRequestFactory.create(**{
            'max_instrument_inputs_per_user': None,
            'max_instrument_inputs': None,
        })
        self.instrument = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
        })

        self.user = User.objects.get_or_create(username='user')[0]
        self.collector = Collector(self.collection_request, **{
            'user': self.user,
        })

    def test_collectionrequest_user_max_stops_is_input_allowed(self):
        def with_config(inputs, user_max):
            CollectedInput.objects.all().delete()

            CollectedInput.objects.bulk_create([
                CollectedInput(data=data, instrument=self.instrument,
                               collection_request=self.collection_request,
                               **self.collector.context) \
                    for data in inputs
            ])

            self.collection_request.max_instrument_inputs_per_user = user_max
            return self.collector.is_input_allowed(self.instrument)

        self.assertEqual(with_config(inputs=[], user_max=2), True)
        self.assertEqual(with_config(inputs=['a'], user_max=2), True)
        self.assertEqual(with_config(inputs=['a', 'b'], user_max=2), False)
        self.assertEqual(with_config(inputs=['a', 'b', 'c'], user_max=2), False)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd'], user_max=2), False)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd', 'e'], user_max=2), False)
        self.assertEqual(with_config(inputs=[], user_max=4), True)
        self.assertEqual(with_config(inputs=['a'], user_max=4), True)
        self.assertEqual(with_config(inputs=['a', 'b'], user_max=4), True)
        self.assertEqual(with_config(inputs=['a', 'b', 'c'], user_max=4), True)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd'], user_max=4), False)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd', 'e'], user_max=5), False)

    def test_collectionrequest_total_max_stops_is_input_allowed(self):
        def with_config(inputs, max):
            CollectedInput.objects.all().delete()

            CollectedInput.objects.bulk_create([
                CollectedInput(data=data, instrument=self.instrument,
                               collection_request=self.collection_request,
                               **self.collector.context) \
                    for data in inputs
            ])

            self.collection_request.max_instrument_inputs = max
            return self.collector.is_input_allowed(self.instrument)

        self.assertEqual(with_config(inputs=[], max=4), True)
        self.assertEqual(with_config(inputs=['a'], max=4), True)
        self.assertEqual(with_config(inputs=['a', 'b'], max=4), True)
        self.assertEqual(with_config(inputs=['a', 'b', 'c'], max=4), True)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd'], max=4), False)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd', 'e'], max=5), False)
        self.assertEqual(with_config(inputs=[], max=5), True)
        self.assertEqual(with_config(inputs=['a'], max=5), True)
        self.assertEqual(with_config(inputs=['a', 'b'], max=5), True)
        self.assertEqual(with_config(inputs=['a', 'b', 'c'], max=5), True)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd'], max=5), True)
        self.assertEqual(with_config(inputs=['a', 'b', 'c', 'd', 'e'], max=5), False)

    def test_responsepolicy_multiple_coerces_bare_inputs_to_lists_in_clean_data(self):
        self.instrument.response_policy.multiple = True
        def with_config(data):
            return self.collector.clean_data(self.instrument, data)

        self.assertEqual(with_config('a'), ['a'])
        self.assertEqual(with_config(['']), [''])
        self.assertEqual(with_config(['a']), ['a'])
        self.assertEqual(with_config(['a', 'b']), ['a', 'b'])

    def test_responsepolicy_non_multiple_stops_lists_in_clean_data(self):
        self.instrument.response_policy.multiple = False
        def with_config(data):
            return self.collector.clean_data(self.instrument, data)

        with self.assertRaises(ValidationError): with_config([])
        with self.assertRaises(ValidationError): with_config([''])
        with self.assertRaises(ValidationError): with_config(['a'])
        with self.assertRaises(ValidationError): with_config(['a', 'b'])
