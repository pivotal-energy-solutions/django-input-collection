"""instrument: conditions can find their gating answer in requests the collector names."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..collection import collectors, resolvers
from ..collection.resolvers import memoize, read_pass, read_pass_cache, resolving_for
from ..models import CollectionInstrument
from . import factories
from .checklists import gate, question


class Cooperative(collectors.Collector):
    __noregister__ = True
    others = ()

    def get_condition_requests(self, instrument):
        return [instrument.collection_request, *self.others]


class HiddenOthers(Cooperative):
    __noregister__ = True

    def filter_condition_inputs(self, queryset):
        return queryset.exclude(data="hidden")


class HideYes(Cooperative):
    __noregister__ = True

    def filter_condition_inputs(self, queryset):
        return queryset.exclude(data="yes")


class CrossRequestTests(TestCase):
    def setUp(self):
        self.a = factories.CollectionRequestFactory.create()
        self.b = factories.CollectionRequestFactory.create()
        self.parent_a = question(self.a, "shared")  # A asks it, unanswered there
        self.parent_b = question(self.b, "shared")
        self.child = question(self.a, "child", order=1)
        gate(self.child, "shared")

    def allowed(self, cls=collectors.Collector, others=()):
        collector = cls(self.a)
        collector.others = others
        return collector.is_instrument_allowed(self.child)

    def answer(self, instrument, request, data="yes"):
        factories.CollectedInputFactory.create(
            instrument=instrument, collection_request=request, data=data
        )

    def test_default_stays_in_its_own_request(self):
        self.answer(self.parent_b, self.b)
        self.assertFalse(self.allowed())

    def test_the_collector_widens_the_search(self):
        self.answer(self.parent_b, self.b)
        self.assertTrue(self.allowed(Cooperative, others=[self.b]))

    def test_own_answer_wins(self):
        self.answer(self.parent_a, self.a, "no")
        self.answer(self.parent_b, self.b, "yes")
        self.assertFalse(self.allowed(Cooperative, others=[self.b]))

    def test_gate_only_in_another_request(self):
        self.parent_a.delete()
        self.answer(self.parent_b, self.b)
        self.assertTrue(self.allowed(Cooperative, others=[self.b]))

    def test_filter_hook_applies(self):
        self.answer(self.parent_b, self.b, "hidden")
        self.assertFalse(self.allowed(HiddenOthers, others=[self.b]))

    def test_pk_conditions_never_leave_the_request(self):
        self.child.conditions.update(data_getter=f"instrument:{self.parent_b.pk}")
        self.answer(self.parent_b, self.b)
        # parent_b is not in request A: the resolver raises and resolve() falls back (fails).
        self.assertFalse(self.allowed(Cooperative, others=[self.b]))

    def test_collectors_filtering_differently_never_share_a_cache_entry(self):
        self.answer(self.parent_b, self.b)
        for order in ((Cooperative, HideYes), (HideYes, Cooperative)):
            with read_pass():
                seen = {cls: self.allowed(cls, others=[self.b]) for cls in order}
            self.assertEqual(seen, {Cooperative: True, HideYes: False})

    def test_search_sets_never_share_a_cache_entry(self):
        self.answer(self.parent_b, self.b)
        for order in ((collectors.Collector, Cooperative), (Cooperative, collectors.Collector)):
            with read_pass():
                seen = {cls: self.allowed(cls, others=[self.b]) for cls in order}
            self.assertEqual(seen, {collectors.Collector: False, Cooperative: True})

    def test_duplicate_measure_uses_the_first_by_ordering(self):
        late = question(self.a, "dup", order=5)
        early = question(self.a, "dup", order=1)  # higher pk, but first by Meta.ordering
        self.assertGreater(early.pk, late.pk)
        self.child.conditions.update(data_getter="instrument:dup")
        self.answer(early, self.a)
        self.assertTrue(self.allowed())

    def test_broken_hooks_warn_but_missing_gates_stay_quiet(self):
        class Broken(Cooperative):
            __noregister__ = True

            def get_condition_requests(self, instrument):
                raise ValueError("broken hook")

        with self.assertLogs(resolvers.log, "WARNING") as logs:
            self.assertFalse(self.allowed(Broken))  # still falls back
        self.assertIn("broken hook", logs.output[0])

        self.child.conditions.update(data_getter="instrument:nowhere")
        with self.assertNoLogs(resolvers.log, "WARNING"):
            self.assertFalse(self.allowed(Cooperative, others=[self.b]))

    def test_current_collector_is_published_only_while_testing(self):
        seen = []

        class Spy(resolvers.Resolver):
            __noregister__ = True
            name, pattern = "spy", ".*"

            def resolve(self, instrument, **context):
                seen.append(resolvers.current_collector())
                return {"data": "x"}

        spy = Spy()
        resolvers.registry.insert(0, spy)
        try:
            self.child.conditions.update(data_getter="spy:x")
            collector = collectors.Collector(self.a)
            collector.is_instrument_allowed(self.child)
        finally:
            resolvers.registry.remove(spy)
        self.assertEqual(seen, [collector])
        self.assertIsNone(resolvers.current_collector())


class ReadPassTests(TestCase):
    def test_memoize_computes_once_per_pass(self):
        calls = []
        compute = lambda: calls.append(1) or len(calls)  # noqa: E731
        with read_pass():
            self.assertEqual(memoize(("k",), compute), 1)
            self.assertEqual(memoize(("k",), compute), 1)
            self.assertIsNotNone(read_pass_cache())
        self.assertEqual(memoize(("k",), compute), 2)  # no pass: always computes
        self.assertIsNone(read_pass_cache())

    def test_nested_pass_keeps_the_outer_index(self):
        sentinel = object()
        with read_pass(index=sentinel):
            with read_pass():
                self.assertIs(resolvers.current_answer_index(), sentinel)
        self.assertIsNone(resolvers.current_answer_index())

    def test_memoize_keeps_a_string_key_whole(self):
        with read_pass():
            self.assertEqual(memoize("abc", lambda: 1), 1)
            self.assertEqual(memoize(("a", "b", "c"), lambda: 2), 2)
            self.assertEqual(memoize("abc", lambda: 3), 1)
            self.assertEqual(memoize(["a", "b", "c"], lambda: 4), 2)

    def test_state_is_restored_after_an_exception(self):
        with self.assertRaises(RuntimeError):
            with read_pass(index=object()):
                with resolving_for(object()):
                    raise RuntimeError
        self.assertIsNone(read_pass_cache())
        self.assertIsNone(resolvers.current_answer_index())
        self.assertIsNone(resolvers.current_collector())


class CacheHitQueryTests(TestCase):
    """A cache hit costs no query per child, even when its collection_request FK isn't loaded."""

    def resolve_children(self, size):
        request = factories.CollectionRequestFactory.create()
        parent = question(request, "shared")
        factories.CollectedInputFactory.create(
            instrument=parent, collection_request=request, data="yes"
        )
        pks = [question(request, f"child-{i}", order=i + 1).pk for i in range(size)]
        children = list(CollectionInstrument.objects.filter(pk__in=pks))
        with read_pass(), resolving_for(collectors.Collector(request)):
            with CaptureQueriesContext(connection) as queries:
                data = [resolvers.resolve(c, "instrument:shared")[1]["data"] for c in children]
        self.assertEqual(data, [["yes"]] * size)
        return len(queries)

    def test_cache_hits_are_free(self):
        small, large = self.resolve_children(3), self.resolve_children(9)
        self.assertEqual(small, large)
        self.assertEqual(small, 2)  # parent instrument + its inputs, once per pass
