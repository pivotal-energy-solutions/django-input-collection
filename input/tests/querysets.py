from django.test import TestCase

from .. import models


CollectedInput = models.get_input_model()

class ContextualQuerySetTests(TestCase):
    def test_static_context_applied_globally(self):
        pass
