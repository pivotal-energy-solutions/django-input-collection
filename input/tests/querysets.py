from django.test import TestCase

from .. import models
from ..models import managers
from . import factories


CollectedInput = models.get_input_model()


class ContextualQuerySetTests(TestCase):
    def test_queryset_has_filter_for_context_method(self):
        self.assertEqual(hasattr(CollectedInput.objects, 'filter_for_context'), True)

    def test_static_context_applies_implicitly(self):
        """ Tests that a queryset 'context' does at least a basic filter. """
        factories.CollectedInputFactory.create_batch(size=2)

        standard_queryset = CollectedInput.objects.all()
        filtered_queryset = CollectedInput.objects.filter_for_context(**{
            'id': 1,
        })

        self.assertEqual(standard_queryset.count(), 2)
        self.assertEqual(filtered_queryset.count(), 1)
        self.assertEqual(filtered_queryset.get().id, 1)
