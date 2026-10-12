"""Question keys, copy labels and the copy-scope ContextVar."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from ..collection.repeat import (
    KEY_SEPARATOR,
    Copy,
    CurrentCopy,
    copy_scope,
    current_copy,
    parse_key,
    question_key,
    read_context,
    render_label,
    scoped_index,
)
from .factories import CollectionRequestFactory
from .repeats import repeat_group


class QuestionKeyTests(SimpleTestCase):
    def test_round_trip(self):
        self.assertEqual(KEY_SEPARATOR, "#")
        self.assertEqual(question_key("door-type", None), "door-type")
        self.assertEqual(question_key("door-type", 2), "door-type#2")
        self.assertEqual(parse_key("door-type"), ("door-type", None))
        self.assertEqual(parse_key("door-type#2"), ("door-type", 2))

    def test_bad_keys_raise(self):
        for key in (
            "door-type#0",
            "door-type#x",
            "door-type#",
            "#2",
            "door-type#-1",
            "a#1#2",
            "",
            "m#\u0663",
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_key(key)


class RenderLabelTests(SimpleTestCase):
    def test_placeholders(self):
        self.assertEqual(render_label("Door {n}", n=2), "Door 2")
        self.assertEqual(render_label("{label} ({n})", n=1, label="Upstairs"), "Upstairs (1)")

    def test_the_default_is_the_group_name_and_ordinal(self):
        self.assertEqual(render_label("", n=3, group_name="Doors"), "Doors 3")
        self.assertEqual(render_label("", n=3), "3")

    def test_other_braces_are_left_alone(self):
        self.assertEqual(render_label("{x} {n}", n=1), "{x} 1")


class CopyScopeTests(SimpleTestCase):
    def test_a_scope_sets_nests_and_resets(self):
        self.assertIsNone(current_copy())
        outer = CurrentCopy(group_id=7, group_slug="doors", index=1)
        with copy_scope(outer):
            self.assertEqual(current_copy(), outer)
            with copy_scope(None):
                self.assertIsNone(current_copy())
            self.assertEqual(current_copy(), outer)
        self.assertIsNone(current_copy())

    def test_a_scope_resets_on_error(self):
        with self.assertRaises(RuntimeError), copy_scope(CurrentCopy(1, "doors", 1)):
            raise RuntimeError
        self.assertIsNone(current_copy())

    def test_copies_are_values(self):
        self.assertEqual(Copy(1, "Door 1"), Copy(index=1, label="Door 1", binding=None))
        self.assertIsNone(CurrentCopy(1, "doors", 2).binding)

    def test_read_context_drops_the_write_copy(self):
        self.assertEqual(read_context({"user": 1, "repeat_index": 2}), {"user": 1})

    def test_scoped_index(self):
        in_group = SimpleNamespace(repeat_group=SimpleNamespace(slug="doors"))
        self.assertEqual(scoped_index(in_group, CurrentCopy(7, "doors", 2)), 2)
        self.assertIsNone(scoped_index(in_group, CurrentCopy(8, "windows", 2)))
        self.assertIsNone(scoped_index(in_group, None))
        self.assertIsNone(scoped_index(SimpleNamespace(), CurrentCopy(7, "doors", 2)))
        self.assertIsNone(
            scoped_index(SimpleNamespace(repeat_group=None), CurrentCopy(7, "doors", 2))
        )


class ScopedIndexSlugTests(TestCase):
    def test_two_group_rows_with_one_slug_are_the_same_group(self):
        """One cloned request per program: each has its own RepeatGroup pk, same slug."""
        first = repeat_group(CollectionRequestFactory.create(), slug="doors")
        second = repeat_group(CollectionRequestFactory.create(), slug="doors")
        self.assertNotEqual(first.pk, second.pk)
        instrument = SimpleNamespace(repeat_group=second)
        copy = CurrentCopy(group_id=first.pk, group_slug=first.slug, index=3)
        self.assertEqual(scoped_index(instrument, copy), 3)
        other = repeat_group(CollectionRequestFactory.create(), slug="windows", name="Windows")
        self.assertIsNone(scoped_index(SimpleNamespace(repeat_group=other), copy))
