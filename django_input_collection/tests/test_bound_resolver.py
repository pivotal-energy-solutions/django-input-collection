"""bound:<dotted path> reads the object the current copy is bound to."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from types import SimpleNamespace

from django.test import SimpleTestCase

from ..collection import resolvers
from ..collection.repeat import CurrentCopy, copy_scope

ANCHOR = SimpleNamespace(pk=1)


class BoundResolverTests(SimpleTestCase):
    def resolve(self, getter, binding=None, copy=True):
        scope = (
            CurrentCopy(group_id=1, group_slug="grills", index=1, binding=binding) if copy else None
        )
        with copy_scope(scope):
            return resolvers.resolve(ANCHOR, getter, fallback="fallback")

    def test_reads_the_bound_object(self):
        resolver, data, error = self.resolve(
            "bound:qty_return_grills", SimpleNamespace(qty_return_grills=1)
        )
        self.assertIsInstance(resolver, resolvers.BoundResolver)
        self.assertIsNone(error)
        self.assertEqual(data, {"data": {"input": [1]}})

    def test_dotted_paths_and_dicts(self):
        system = SimpleNamespace(ducts={"leakage": 4.5})
        self.assertEqual(self.resolve("bound:ducts.leakage", system)[1], {"data": {"input": [4.5]}})

    def test_no_copy_or_no_binding_falls_back(self):
        for kwargs in ({"copy": False}, {"binding": None}):
            with self.subTest(**kwargs):
                _resolver, data, error = self.resolve("bound:qty_return_grills", **kwargs)
                self.assertIsInstance(error, ValueError)
                self.assertEqual(data, {"data": "fallback"})

    def test_registered_once(self):
        self.assertEqual([r.name for r in resolvers.registry].count("bound"), 1)
