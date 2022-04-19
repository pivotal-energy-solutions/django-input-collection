# -*- coding: utf-8 -*-
from django.test import TestCase

from .. import models
from . import factories


CollectedInput = models.get_input_model()


class ContextualQuerySetTests(TestCase):
    def test_queryset_has_filter_for_context_method(self):
        self.assertEqual(hasattr(CollectedInput.objects, "filter_for_context"), True)

    def test_queryset_context_applies_filter(self):
        """Tests that a queryset 'context' does at least a basic filter."""
        inputs = factories.CollectedInputFactory.create_batch(size=2)

        standard_queryset = CollectedInput.objects.all()
        filtered_queryset = CollectedInput.objects.filter_for_context(
            **{
                "id": inputs[1].id,
            }
        )

        self.assertEqual(standard_queryset.count(), 2)
        self.assertEqual(filtered_queryset.count(), 1)
        self.assertEqual(filtered_queryset.get().id, inputs[1].id)
