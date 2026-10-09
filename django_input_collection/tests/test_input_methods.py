"""InputMethod error lookup: failed cleans surface as ValidationErrors with the method's message."""

__author__ = "Steven K"
__date__ = "10/09/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven K"]

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from ..collection.methods.base import InputMethod
from ..collection.methods.defaults import FloatMethod, IntegerMethod


class InputMethodErrorTests(SimpleTestCase):
    def test_integer_method_rejects_non_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            IntegerMethod().clean_input("x")
        self.assertEqual(ctx.exception.messages, ["Please enter a valid integer."])

    def test_float_method_rejects_non_float(self):
        with self.assertRaises(ValidationError) as ctx:
            FloatMethod().clean_input("x")
        self.assertEqual(ctx.exception.messages, ["Please enter a valid float."])

    def test_valid_values_still_clean(self):
        self.assertEqual(IntegerMethod().clean_input("3"), 3)
        self.assertEqual(FloatMethod().clean_input("2.5"), 2.5)

    def test_base_message_formats_the_exception(self):
        def boom(data):
            raise ValueError("bad value")

        with self.assertRaises(ValidationError) as ctx:
            InputMethod(cleaner=boom).clean_input("x")
        self.assertEqual(ctx.exception.messages, ["bad value"])

    def test_most_specific_exception_class_wins(self):
        def boom(data):
            raise ValueError("bad value")

        errors = {LookupError: "lookup", ValueError: "value", Exception: "generic"}
        method = InputMethod(cleaner=boom, errors=errors)
        with self.assertRaises(ValidationError) as ctx:
            method.clean_input("x")
        self.assertEqual(ctx.exception.messages, ["value"])

    def test_tuple_keys_match_any_member(self):
        def boom(data):
            raise KeyError("k")

        method = InputMethod(cleaner=boom, errors={(KeyError, TypeError): "key or type"})
        with self.assertRaises(ValidationError) as ctx:
            method.clean_input("x")
        self.assertEqual(ctx.exception.messages, ["key or type"])
