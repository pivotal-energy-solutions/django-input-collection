from django.test import TestCase

from ..collection import collectors


class CollectorRegistrationTests(TestCase):
    def test_basescollectors_are_unregistered(self):
        """ Verifies that the base API collector subclass is NOT directly usable. """
        self.assertNotIn(collectors.BaseCollector, collectors.registry)
        self.assertNotIn(collectors.BaseAPICollector, collectors.registry)

    def test_basecollectors_cannot_be_inspected_for_registration_identifier(self):
        """ Verifies that the base API collector subclass is NOT directly usable. """
        self.assertEqual(hasattr(collectors.BaseCollector, '__noregister__'), True)
        self.assertEqual(collectors.BaseCollector.__noregister__, True)
        with self.assertRaises(collectors.CollectorException):
            collectors.BaseCollector.get_identifier()

        self.assertEqual(hasattr(collectors.BaseAPICollector, '__noregister__'), True)
        self.assertEqual(collectors.BaseAPICollector.__noregister__, True)
        with self.assertRaises(collectors.CollectorException):
            collectors.BaseAPICollector.get_identifier()

    def test_basecollectors_cannot_be_registered(self):
        """ Verifies that the base API collector subclass is NOT directly usable. """
        with self.assertRaises(collectors.CollectorException):
            collectors.BaseCollector.register()

    def test_collector_is_registered_by_default(self):
        """ Verifies that the base Collector is usable out of the box. """
        self.assertIn(collectors.Collector.get_identifier(), collectors.registry)
        self.assertEqual(collectors.registry[collectors.Collector.get_identifier()], collectors.Collector)
