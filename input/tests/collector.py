from inspect import isclass

from django.test import TestCase

from ..collection import collectors, InputMethod
from . import factories


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


class CollectorTests(TestCase):
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
        with self.assertRaises(KeyError):
            with_methodkwargs({'bar': 'bar'})

        # Now prove the KeyError isn't a fluke
        CustomFooMethod.bar = None
        self.assertEqual(with_methodkwargs({'bar': 'bar'}).data, {'foo1': 'foo1', 'foo2': None, 'bar': 'bar'})
