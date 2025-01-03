from django.test import TestCase

from .. import models
from ..collection.matchers import test_condition_case, matchers, resolve_matcher
from . import factories


CollectedInput = models.get_input_model()


class CoreMatcherTests(TestCase):
    """
    Verifies behavior of the underlying ``collection.matchers.test_condition_case`` function.
    """

    def test_matcher_resolver(self):
        self.assertEqual(resolve_matcher("all-custom"), matchers.all_custom)
        self.assertEqual(resolve_matcher("all_custom"), matchers.all_custom)

    def test_matcher_errors_on_bad_match_type(self):
        with self.assertRaises(AttributeError):
            resolve_matcher("foo")

        with self.assertRaises(AttributeError):
            test_condition_case("data", match_type="foo")

    def test_matcher_accepts_bare_input(self):
        """Verifies that a single data input arg is cast to a list."""
        self.assertEqual(
            test_condition_case("a", match_type="all-suggested", suggested_values=["a", "b", "c"]),
            True,
        )
        self.assertEqual(
            test_condition_case("a", match_type="one-suggested", suggested_values=["a", "b", "c"]),
            True,
        )
        self.assertEqual(
            test_condition_case("a", match_type="all-custom", suggested_values=["a", "b", "c"]),
            False,
        )
        self.assertEqual(
            test_condition_case("a", match_type="one-custom", suggested_values=["a", "b", "c"]),
            False,
        )

    def test_matcher_accepts_list_input(self):
        """Verifies that a data list input arg is taken as it is."""
        self.assertEqual(
            test_condition_case(
                ["a"], match_type="all-suggested", suggested_values=["a", "b", "c"]
            ),
            True,
        )
        self.assertEqual(
            test_condition_case(
                ["a"], match_type="one-suggested", suggested_values=["a", "b", "c"]
            ),
            True,
        )
        self.assertEqual(
            test_condition_case(["a"], match_type="all-custom", suggested_values=["a", "b", "c"]),
            False,
        )
        self.assertEqual(
            test_condition_case(["a"], match_type="one-custom", suggested_values=["a", "b", "c"]),
            False,
        )

    def test_matcher_accepts_valuesqueryset_input(self):
        """Verifies that a data list input arg is taken as it is."""
        factories.CollectedInputFactory.create(
            **{
                "data": "a",
            }
        )
        valueslist = CollectedInput.objects.values_list("data", flat=True)

        self.assertEqual(
            test_condition_case(
                valueslist, match_type="all-suggested", suggested_values=["a", "b", "c"]
            ),
            True,
        )
        self.assertEqual(
            test_condition_case(
                valueslist, match_type="one-suggested", suggested_values=["a", "b", "c"]
            ),
            True,
        )
        self.assertEqual(
            test_condition_case(
                valueslist, match_type="all-custom", suggested_values=["a", "b", "c"]
            ),
            False,
        )
        self.assertEqual(
            test_condition_case(
                valueslist, match_type="one-custom", suggested_values=["a", "b", "c"]
            ),
            False,
        )


class MatchTypesTests(TestCase):
    """Verifies behavior of the individual matchers."""

    def test_match_type_any(self):
        self.assertEqual(matchers.any("foo"), True)
        self.assertEqual(matchers.any(["foo"]), True)
        self.assertEqual(matchers.any(["foo", "bar"]), True)
        self.assertEqual(matchers.any(None), False)
        self.assertEqual(matchers.any([]), False)
        self.assertEqual(matchers.any(""), False)
        self.assertEqual(matchers.any([""]), False)

    def test_match_type_none(self):
        self.assertEqual(matchers.none("foo"), False)
        self.assertEqual(matchers.none(["foo"]), False)
        self.assertEqual(matchers.none(["foo", "bar"]), False)
        self.assertEqual(matchers.none(None), True)
        self.assertEqual(matchers.none(""), True)
        self.assertEqual(matchers.none([]), True)
        self.assertEqual(matchers.none([""]), True)

    def test_match_type_all_suggested(self):
        self.assertEqual(matchers.all_suggested("a", suggested_values=["a", "b", "c"]), True)
        self.assertEqual(matchers.all_suggested(["a"], suggested_values=["a", "b", "c"]), True)
        self.assertEqual(matchers.all_suggested(["a", "b"], suggested_values=["a", "b", "c"]), True)
        self.assertEqual(
            matchers.all_suggested(["a", "b", "c"], suggested_values=["a", "b", "c"]), True
        )
        self.assertEqual(
            matchers.all_suggested(["a", "b", "c", "d"], suggested_values=["a", "b", "c"]), False
        )
        self.assertEqual(matchers.all_suggested("d", suggested_values=["a", "b", "c"]), False)
        self.assertEqual(matchers.all_suggested(["d"], suggested_values=["a", "b", "c"]), False)

    def test_match_type_one_suggested(self):
        self.assertEqual(matchers.one_suggested("a", suggested_values=["a", "b", "c"]), True)
        self.assertEqual(matchers.one_suggested(["a"], suggested_values=["a", "b", "c"]), True)
        self.assertEqual(matchers.one_suggested(["a", "b"], suggested_values=["a", "b", "c"]), True)
        self.assertEqual(
            matchers.one_suggested(["a", "b", "c"], suggested_values=["a", "b", "c"]), True
        )
        self.assertEqual(
            matchers.one_suggested(["a", "b", "c", "d"], suggested_values=["a", "b", "c"]), True
        )
        self.assertEqual(matchers.one_suggested("d", suggested_values=["a", "b", "c"]), False)
        self.assertEqual(matchers.one_suggested(["d"], suggested_values=["a", "b", "c"]), False)

    def test_match_type_all_custom(self):
        self.assertEqual(matchers.all_custom("a", suggested_values=["a", "b", "c"]), False)
        self.assertEqual(matchers.all_custom(["a"], suggested_values=["a", "b", "c"]), False)
        self.assertEqual(matchers.all_custom(["a", "b"], suggested_values=["a", "b", "c"]), False)
        self.assertEqual(
            matchers.all_custom(["a", "b", "c"], suggested_values=["a", "b", "c"]), False
        )
        self.assertEqual(
            matchers.all_custom(["a", "b", "c", "d"], suggested_values=["a", "b", "c"]), False
        )
        self.assertEqual(matchers.all_custom("d", suggested_values=["a", "b", "c"]), True)
        self.assertEqual(matchers.all_custom(["d"], suggested_values=["a", "b", "c"]), True)

    def test_match_type_one_custom(self):
        self.assertEqual(matchers.one_custom("a", suggested_values=["a", "b", "c"]), False)
        self.assertEqual(matchers.one_custom(["a"], suggested_values=["a", "b", "c"]), False)
        self.assertEqual(matchers.one_custom(["a", "b"], suggested_values=["a", "b", "c"]), False)
        self.assertEqual(
            matchers.one_custom(["a", "b", "c"], suggested_values=["a", "b", "c"]), False
        )
        self.assertEqual(
            matchers.one_custom(["a", "b", "c", "d"], suggested_values=["a", "b", "c"]), True
        )
        self.assertEqual(matchers.one_custom("d", suggested_values=["a", "b", "c"]), True)
        self.assertEqual(matchers.one_custom(["d"], suggested_values=["a", "b", "c"]), True)

    def test_match_type_match(self):
        self.assertEqual(matchers.match("foo", match_data="foo"), True)
        self.assertEqual(matchers.match("foo", match_data="Foo"), False)
        self.assertEqual(matchers.match("foo", match_data="xfoox"), False)
        self.assertEqual(matchers.match("foo", match_data="bar"), False)
        self.assertEqual(matchers.match("foo", match_data="Bar"), False)
        self.assertEqual(matchers.match("foo", match_data="xbarx"), False)
        self.assertEqual(matchers.match(["foo"], match_data="foo"), True)
        self.assertEqual(matchers.match("foo", match_data=["foo"]), False)
        self.assertEqual(matchers.match(["foo"], match_data=["foo"]), True)

    def test_match_type_match_ints(self):
        self.assertEqual(matchers.match([1], match_data=["1"]), True)
        self.assertEqual(matchers.match(["1"], match_data=[1]), True)
        self.assertEqual(matchers.match([1], match_data="1"), True)
        self.assertEqual(matchers.match("1", match_data=[1]), False)

    def test_match_type_match_floats(self):
        self.assertEqual(matchers.match([13.0], match_data=["13.0"]), True)
        self.assertEqual(matchers.match([13.1], match_data=["13.1"]), True)
        self.assertEqual(matchers.match(["19.0"], match_data=[19.0]), True)
        self.assertEqual(matchers.match(["19.1"], match_data=[19.1]), True)
        self.assertEqual(matchers.match([12.2], match_data="12.2"), True)
        self.assertEqual(matchers.match([12.0], match_data="12.0"), True)
        self.assertEqual(matchers.match("11.0", match_data=[11.0]), False)

    def test_match_type_mismatch(self):
        self.assertEqual(matchers.mismatch("foo", match_data="foo"), False)
        self.assertEqual(matchers.mismatch("foo", match_data="Foo"), True)
        self.assertEqual(matchers.mismatch("foo", match_data="xfoox"), True)
        self.assertEqual(matchers.mismatch("foo", match_data="bar"), True)
        self.assertEqual(matchers.mismatch("foo", match_data="Bar"), True)
        self.assertEqual(matchers.mismatch("foo", match_data="xbarx"), True)
        self.assertEqual(matchers.mismatch(["foo"], match_data="foo"), False)
        self.assertEqual(matchers.mismatch("foo", match_data=["foo"]), True)
        self.assertEqual(matchers.mismatch(["foo"], match_data=["foo"]), False)

    def test_match_type_mismatch_ints(self):
        self.assertEqual(matchers.mismatch([1], match_data=["1"]), False)
        self.assertEqual(matchers.mismatch(["1"], match_data=[1]), False)
        self.assertEqual(matchers.mismatch([1], match_data=["1"]), False)
        self.assertEqual(matchers.mismatch([1], match_data="1"), False)
        self.assertEqual(matchers.mismatch("1", match_data=[1]), True)

    def test_match_type_mismatch_floats(self):
        self.assertEqual(matchers.mismatch([13.0], match_data=["13.0"]), False)
        self.assertEqual(matchers.mismatch([13.1], match_data=["13.1"]), False)
        self.assertEqual(matchers.mismatch(["19.0"], match_data=[19.0]), False)
        self.assertEqual(matchers.mismatch(["19.1"], match_data=[19.1]), False)
        self.assertEqual(matchers.mismatch([12.2], match_data="12.2"), False)
        self.assertEqual(matchers.mismatch([12.0], match_data="12.0"), False)
        self.assertEqual(matchers.mismatch("11.0", match_data=[11.0]), True)

    def test_match_type_contains(self):
        self.assertEqual(matchers.contains("foo", match_data="foo"), True)
        self.assertEqual(matchers.contains("foo", match_data="Foo"), False)
        self.assertEqual(matchers.contains("foo", match_data="xfoox"), False)
        self.assertEqual(matchers.contains("foo", match_data="bar"), False)
        self.assertEqual(matchers.contains("foo", match_data="Bar"), False)
        self.assertEqual(matchers.contains("foo", match_data="xbarx"), False)

        self.assertEqual(matchers.contains("xfooxbarx", match_data="foo"), True)
        self.assertEqual(matchers.contains("xfooxbarx", match_data="Foo"), False)
        self.assertEqual(matchers.contains("xfooxbarx", match_data="xfoox"), True)
        self.assertEqual(matchers.contains("xfooxbarx", match_data="bar"), True)
        self.assertEqual(matchers.contains("xfooxbarx", match_data="Bar"), False)
        self.assertEqual(matchers.contains("xfooxbarx", match_data="xbarx"), True)
        self.assertEqual(matchers.contains(["xfooxbarx"], match_data="foo"), True)

    def test_match_type_not_contains(self):
        self.assertEqual(matchers.not_contains("foo", match_data="foo"), False)
        self.assertEqual(matchers.not_contains("foo", match_data="Foo"), True)
        self.assertEqual(matchers.not_contains("foo", match_data="xfoox"), True)
        self.assertEqual(matchers.not_contains("foo", match_data="bar"), True)
        self.assertEqual(matchers.not_contains("foo", match_data="Bar"), True)
        self.assertEqual(matchers.not_contains("foo", match_data="xbarx"), True)

        self.assertEqual(matchers.not_contains("xfooxbarx", match_data="foo"), False)
        self.assertEqual(matchers.not_contains("xfooxbarx", match_data="Foo"), True)
        self.assertEqual(matchers.not_contains("xfooxbarx", match_data="xfoox"), False)
        self.assertEqual(matchers.not_contains("xfooxbarx", match_data="bar"), False)
        self.assertEqual(matchers.not_contains("xfooxbarx", match_data="Bar"), True)
        self.assertEqual(matchers.not_contains("xfooxbarx", match_data="xbarx"), False)
        self.assertEqual(matchers.not_contains(["xfooxbarx"], match_data="foo"), False)

    def test_match_one(self):
        """The stuff on the left is almost always a list (REM/Rate) match data may or may not be."""
        self.assertEqual(matchers.one([5], match_data=5), True)
        self.assertEqual(matchers.one([5], match_data="5"), True)
        self.assertEqual(matchers.one([5], match_data="3"), False)
        self.assertEqual(matchers.one([5], match_data=["3"]), False)
        self.assertEqual(matchers.one([5], match_data=3), False)
        self.assertEqual(matchers.one([4, 5], match_data=5), True)
        self.assertEqual(matchers.one([4, 5], match_data="5"), True)
        self.assertEqual(matchers.one([4, 5], match_data=[4]), True)
        self.assertEqual(matchers.one([4, 5], match_data=[4, 5]), True)
        self.assertEqual(matchers.one([4], match_data=[4, 5]), True)
        self.assertEqual(matchers.one([4, 4, 2], match_data=4), True)
        self.assertEqual(matchers.one([4, 4, 2], match_data=4), True)

    def test_match_zero(self):
        """Match zero"""
        self.assertEqual(matchers.zero([5], match_data=5), False)
        self.assertEqual(matchers.zero([5], match_data="5"), False)
        self.assertEqual(matchers.zero([5], match_data="3"), True)
        self.assertEqual(matchers.zero([4, 5], match_data=5), False)
        self.assertEqual(matchers.zero([4, 5], match_data="5"), False)
        self.assertEqual(matchers.zero([4, 5], match_data=[4]), False)
        self.assertEqual(matchers.zero([4, 5], match_data=[4, 5]), False)
        self.assertEqual(matchers.zero([4], match_data=[4, 5]), False)
        self.assertEqual(matchers.zero([4, 4, 2], match_data=4), False)
        self.assertEqual(matchers.zero([4, 4, 2], match_data=4), False)


class SingleConditionGroupRequirementTypesTests(TestCase):
    def test_group_cases_requirement_type_all_pass(self):
        """Verifies the AND requirement for a group with a pair of cases."""
        group = factories.ConditionGroupFactory.create(
            **{
                "requirement_type": "all-pass",
                "cases": [
                    # A non-suggested response
                    factories.CaseFactory.create(match_type="all-custom"),
                    # That also contains 'foo'
                    factories.CaseFactory.create(match_type="contains", match_data="foo"),
                ],
            }
        )

        self.assertEqual(group.test("a"), False)
        self.assertEqual(group.test("foo"), True)
        self.assertEqual(group.test("xfoox"), True)
        self.assertEqual(group.test("bar"), False)
        self.assertEqual(group.test(["foo", "bar"]), True)
        self.assertEqual(group.test(["bar"]), False)
        self.assertEqual(group.test(["xfoox"]), True)

        self.assertEqual(group.test("foo", suggested_values=["foo"]), False)
        self.assertEqual(group.test("xfoox", suggested_values=["foo"]), True)
        self.assertEqual(group.test(["foo", "xfoox"], suggested_values=["foo"]), False)

        self.assertEqual(group.test("bar", suggested_values=["bar"]), False)
        self.assertEqual(group.test("xbarx", suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xbarx"], suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xfoox"], suggested_values=["bar"]), False)

    def test_group_cases_requirement_type_one_pass(self):
        """Verifies the OR requirement for a group with a pair of cases."""
        group = factories.ConditionGroupFactory.create(
            **{
                "requirement_type": "one-pass",
                "cases": [
                    # A non-suggested response
                    factories.CaseFactory.create(match_type="all-custom"),
                    # Or a suggested response that contains 'foo'
                    factories.CaseFactory.create(match_type="contains", match_data="foo"),
                ],
            }
        )

        self.assertEqual(group.test("a"), True)
        self.assertEqual(group.test("foo"), True)
        self.assertEqual(group.test("xfoox"), True)
        self.assertEqual(group.test("bar"), True)
        self.assertEqual(group.test(["foo", "bar"]), True)
        self.assertEqual(group.test(["bar"]), True)
        self.assertEqual(group.test(["xfoox"]), True)

        self.assertEqual(group.test("foo", suggested_values=["foo"]), True)
        self.assertEqual(group.test("xfoox", suggested_values=["foo"]), True)
        self.assertEqual(group.test(["foo", "xfoox"], suggested_values=["foo"]), True)

        self.assertEqual(group.test("bar", suggested_values=["bar"]), False)
        self.assertEqual(group.test("xbarx", suggested_values=["bar"]), True)
        self.assertEqual(group.test(["bar", "xbarx"], suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xfoox"], suggested_values=["bar"]), True)

    def test_group_cases_requirement_type_all_fail(self):
        """Verifies the NONE requirement for a group with a pair of cases."""
        group = factories.ConditionGroupFactory.create(
            **{
                "requirement_type": "all-fail",
                "cases": [
                    # A non-custom response (synonymous with 'all-suggested', once we invert)
                    factories.CaseFactory.create(match_type="all-custom"),
                    # That doesn't contain 'foo' (synonymous with 'not-contains', once we invert)
                    factories.CaseFactory.create(match_type="contains", match_data="foo"),
                ],
            }
        )

        self.assertEqual(group.test("a"), False)
        self.assertEqual(group.test("foo"), False)
        self.assertEqual(group.test("xfoox"), False)
        self.assertEqual(group.test("bar"), False)
        self.assertEqual(group.test(["foo", "bar"]), False)
        self.assertEqual(group.test(["bar"]), False)
        self.assertEqual(group.test(["xfoox"]), False)

        self.assertEqual(group.test("foo", suggested_values=["foo"]), False)
        self.assertEqual(group.test("xfoox", suggested_values=["foo"]), False)
        self.assertEqual(group.test(["foo", "xfoox"], suggested_values=["foo"]), False)

        self.assertEqual(group.test("bar", suggested_values=["bar"]), True)
        self.assertEqual(group.test("xbarx", suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xbarx"], suggested_values=["bar"]), True)
        self.assertEqual(group.test(["bar", "xfoox"], suggested_values=["bar"]), False)


class StackedConditionGroupRequirementTypesTests(TestCase):
    def test_group_child_groups_requirement_type_all_pass(self):
        """Verifies the AND requirement for a group with subgroups."""
        group = factories.ConditionGroupFactory.create(
            **{
                "requirement_type": "all-pass",
                "child_groups": [
                    factories.ConditionGroupFactory.create(
                        **{
                            "requirement_type": "all-pass",
                            "cases": [
                                # A non-suggested response
                                factories.CaseFactory.create(match_type="all-custom"),
                            ],
                        }
                    ),
                    factories.ConditionGroupFactory.create(
                        **{
                            "requirement_type": "all-pass",
                            "cases": [
                                # That also contains 'foo'
                                factories.CaseFactory.create(
                                    match_type="contains", match_data="foo"
                                ),
                            ],
                        }
                    ),
                ],
            }
        )

        self.assertEqual(group.test("a"), False)
        self.assertEqual(group.test("foo"), True)
        self.assertEqual(group.test("xfoox"), True)
        self.assertEqual(group.test("bar"), False)
        self.assertEqual(group.test(["foo", "bar"]), True)
        self.assertEqual(group.test(["bar"]), False)
        self.assertEqual(group.test(["xfoox"]), True)

        self.assertEqual(group.test("foo", suggested_values=["foo"]), False)
        self.assertEqual(group.test("xfoox", suggested_values=["foo"]), True)
        self.assertEqual(group.test(["foo", "xfoox"], suggested_values=["foo"]), False)

        self.assertEqual(group.test("bar", suggested_values=["bar"]), False)
        self.assertEqual(group.test("xbarx", suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xbarx"], suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xfoox"], suggested_values=["bar"]), False)

    def test_group_cases_requirement_type_one_pass(self):
        """Verifies the OR requirement for a group with subgroups."""
        group = factories.ConditionGroupFactory.create(
            **{
                "requirement_type": "one-pass",
                "child_groups": [
                    factories.ConditionGroupFactory.create(
                        **{
                            "requirement_type": "all-pass",
                            "cases": [
                                # A non-suggested response
                                factories.CaseFactory.create(match_type="all-custom"),
                            ],
                        }
                    ),
                    factories.ConditionGroupFactory.create(
                        **{
                            "requirement_type": "all-pass",
                            "cases": [
                                # Or a suggested response that contains 'foo'
                                factories.CaseFactory.create(
                                    match_type="contains", match_data="foo"
                                ),
                            ],
                        }
                    ),
                ],
            }
        )

        self.assertEqual(group.test("a"), True)
        self.assertEqual(group.test("foo"), True)
        self.assertEqual(group.test("xfoox"), True)
        self.assertEqual(group.test("bar"), True)
        self.assertEqual(group.test(["foo", "bar"]), True)
        self.assertEqual(group.test(["bar"]), True)
        self.assertEqual(group.test(["xfoox"]), True)

        self.assertEqual(group.test("foo", suggested_values=["foo"]), True)
        self.assertEqual(group.test("xfoox", suggested_values=["foo"]), True)
        self.assertEqual(group.test(["foo", "xfoox"], suggested_values=["foo"]), True)

        self.assertEqual(group.test("bar", suggested_values=["bar"]), False)
        self.assertEqual(group.test("xbarx", suggested_values=["bar"]), True)
        self.assertEqual(group.test(["bar", "xbarx"], suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xfoox"], suggested_values=["bar"]), True)

    def test_group_cases_requirement_type_all_fail(self):
        """Verifies the NONE requirement for a group with subgroups."""
        group = factories.ConditionGroupFactory.create(
            **{
                "requirement_type": "all-fail",
                "child_groups": [
                    factories.ConditionGroupFactory.create(
                        **{
                            "requirement_type": "all-pass",
                            "cases": [
                                # A non-custom response (synonymous with 'all-suggested', once we invert)
                                factories.CaseFactory.create(match_type="all-custom"),
                            ],
                        }
                    ),
                    factories.ConditionGroupFactory.create(
                        **{
                            "requirement_type": "all-pass",
                            "cases": [
                                # That doesn't contain 'foo' (synonymous with 'not-contains', once we
                                # invert)
                                factories.CaseFactory.create(
                                    match_type="contains", match_data="foo"
                                ),
                            ],
                        }
                    ),
                ],
            }
        )

        self.assertEqual(group.test("a"), False)
        self.assertEqual(group.test("foo"), False)
        self.assertEqual(group.test("xfoox"), False)
        self.assertEqual(group.test("bar"), False)
        self.assertEqual(group.test(["foo", "bar"]), False)
        self.assertEqual(group.test(["bar"]), False)
        self.assertEqual(group.test(["xfoox"]), False)

        self.assertEqual(group.test("foo", suggested_values=["foo"]), False)
        self.assertEqual(group.test("xfoox", suggested_values=["foo"]), False)
        self.assertEqual(group.test(["foo", "xfoox"], suggested_values=["foo"]), False)

        self.assertEqual(group.test("bar", suggested_values=["bar"]), True)
        self.assertEqual(group.test("xbarx", suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xbarx"], suggested_values=["bar"]), True)
        self.assertEqual(group.test(["bar", "xfoox"], suggested_values=["bar"]), False)

    def test_group_assesses_subgroups_and_local_cases(self):
        group = factories.ConditionGroupFactory.create(
            **{
                "requirement_type": "all-pass",
                "cases": [
                    # A non-suggested response
                    factories.CaseFactory.create(match_type="all-custom"),
                ],
                "child_groups": [
                    factories.ConditionGroupFactory.create(
                        **{
                            "requirement_type": "all-pass",
                            "cases": [
                                # That also contains 'foo'
                                factories.CaseFactory.create(
                                    match_type="contains", match_data="foo"
                                ),
                            ],
                        }
                    ),
                ],
            }
        )

        self.assertEqual(group.test("a"), False)
        self.assertEqual(group.test("foo"), True)
        self.assertEqual(group.test("xfoox"), True)
        self.assertEqual(group.test("bar"), False)
        self.assertEqual(group.test(["foo", "bar"]), True)
        self.assertEqual(group.test(["bar"]), False)
        self.assertEqual(group.test(["xfoox"]), True)

        self.assertEqual(group.test("foo", suggested_values=["foo"]), False)
        self.assertEqual(group.test("xfoox", suggested_values=["foo"]), True)
        self.assertEqual(group.test(["foo", "xfoox"], suggested_values=["foo"]), False)

        self.assertEqual(group.test("bar", suggested_values=["bar"]), False)
        self.assertEqual(group.test("xbarx", suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xbarx"], suggested_values=["bar"]), False)
        self.assertEqual(group.test(["bar", "xfoox"], suggested_values=["bar"]), False)


class ConditionTests(TestCase):
    def test_condition_gets_values_from_data_getter(self):
        """
        Verifies that a Condition on a specific Instrument gathers the required data to for the
        ConditionGroups to perform its assessment.
        """
        parent_instrument = factories.CollectionInstrumentFactory.create(
            **{
                "id": 1,
                "collection_request__id": 1,
            }
        )
        condition = factories.ConditionFactory.create(
            **{
                "data_getter": "instrument:%d" % (parent_instrument.id,),
                "instrument": factories.CollectionInstrumentFactory.create(
                    **{
                        "id": 2,
                        "collection_request__id": 1,
                    }
                ),
                "condition_group": factories.ConditionGroupFactory.create(
                    **{
                        "requirement_type": "all-pass",
                        "cases": [
                            factories.CaseFactory.create(match_type="all-custom"),
                        ],
                    }
                ),
            }
        )

        factories.CollectedInputFactory.create(
            **{
                "instrument__id": 1,
                "data": "foo",
            }
        )

        self.assertEqual(condition.test(), True)
        self.assertEqual(condition.test(suggested_values=["foo"]), True)
        self.assertEqual(condition.test(suggested_values=["bar"]), True)

    def test_multiple_conditions_for_single_instrument_must_all_pass(self):
        """
        Verifies that multiple parent instruments are able to condtribute to the unlocking of a
        single dependent one.
        """

        instrument = factories.CollectionInstrumentFactory.create(
            **{
                "id": 3,
                "collection_request__id": 1,
            }
        )

        # Parent 1 input must contain 'foo'
        parent_instrument1 = factories.CollectionInstrumentFactory.create(
            **{
                "id": 1,
                "collection_request__id": 1,
            }
        )
        factories.ConditionFactory.create(
            **{
                "data_getter": "instrument:%d" % (parent_instrument1.id,),
                "instrument": instrument,
                "condition_group": factories.ConditionGroupFactory.create(
                    **{
                        "requirement_type": "all-pass",
                        "cases": [
                            factories.CaseFactory.create(match_type="contains", match_data="foo"),
                        ],
                    }
                ),
            }
        )
        parent_instrument2 = factories.CollectionInstrumentFactory.create(
            **{
                "id": 2,
                "collection_request__id": 1,
            }
        )
        # Parent 2 input must contain 'bar'
        factories.ConditionFactory.create(
            **{
                "data_getter": "instrument:%d" % (parent_instrument2.id,),
                "instrument": instrument,
                "condition_group": factories.ConditionGroupFactory.create(
                    **{
                        "requirement_type": "all-pass",
                        "cases": [
                            factories.CaseFactory.create(match_type="contains", match_data="bar"),
                        ],
                    }
                ),
            }
        )

        def test_conditions(*input_pairs):
            for id, data in input_pairs:
                models.CollectedInput.objects.filter(id=id).update(data=data)
            return instrument.test_conditions()

        factories.CollectedInputFactory.create(
            id=1, instrument__id=parent_instrument1.id, data="dummy"
        )
        factories.CollectedInputFactory.create(
            id=2, instrument__id=parent_instrument2.id, data="dummy"
        )
        self.assertEqual(test_conditions([1, "foo"], [2, "bar"]), True)
        self.assertEqual(test_conditions([1, "xfoox"], [2, "xbarx"]), True)
        self.assertEqual(test_conditions([1, "xfooxbarx"], [2, "x"]), False)
        self.assertEqual(test_conditions([1, "x"], [2, "xbarxfoox"]), False)
        self.assertEqual(test_conditions([1, "x"], [2, "xbarxfoox"]), False)
        self.assertEqual(test_conditions([1, "x"], [2, "x"]), False)

    def test_multiple_conditions_for_single_instrument_one_pass(self):
        """
        Verifies that multiple parent instruments are able to condtribute to the unlocking of a
        single dependent one.
        """

        instrument = factories.CollectionInstrumentFactory.create(
            id=1, collection_request__id=1, test_requirement_type="one-pass"
        )
        child_instrument1 = factories.CollectionInstrumentFactory(id=2, collection_request__id=1)
        factories.ConditionFactory.create(
            instrument=instrument,
            data_getter=f"instrument:{child_instrument1.id}",
            condition_group=factories.ConditionGroupFactory.create(
                requirement_type="all-pass",
                cases=[factories.CaseFactory.create(match_type="match", match_data="yes")],
            ),
        )
        child_instrument2 = factories.CollectionInstrumentFactory(id=3, collection_request__id=1)
        factories.ConditionFactory.create(
            instrument=instrument,
            data_getter=f"instrument:{child_instrument2.id}",
            condition_group=factories.ConditionGroupFactory.create(
                requirement_type="all-pass",
                cases=[factories.CaseFactory.create(match_type="match", match_data="yes")],
            ),
        )

        def test_conditions(*input_pairs):
            for id, data in input_pairs:
                models.CollectedInput.objects.filter(id=id).update(data=data)
            return instrument.test_conditions()

        factories.CollectedInputFactory.create(
            id=1, instrument__id=child_instrument1.id, data="dummy"
        )
        factories.CollectedInputFactory.create(
            id=2, instrument__id=child_instrument2.id, data="dummy"
        )
        self.assertEqual(test_conditions([1, "foo"], [2, "bar"]), False)
        self.assertEqual(test_conditions([1, "yes"], [2, "yes"]), True)
        self.assertEqual(test_conditions([1, "yes"], [2, "no"]), True)
        self.assertEqual(test_conditions([1, "no"], [2, "yes"]), True)
        self.assertEqual(test_conditions([1, "no"], [2, "no"]), False)

    def test_multiple_conditions_for_single_instrument_all_pass(self):
        """
        Verifies that multiple parent instruments are able to condtribute to the unlocking of a
        single dependent one.
        """

        instrument = factories.CollectionInstrumentFactory.create(
            id=1, collection_request__id=1, test_requirement_type="all-pass"
        )
        child_instrument1 = factories.CollectionInstrumentFactory(id=2, collection_request__id=1)
        factories.ConditionFactory.create(
            instrument=instrument,
            data_getter=f"instrument:{child_instrument1.id}",
            condition_group=factories.ConditionGroupFactory.create(
                requirement_type="all-pass",
                cases=[factories.CaseFactory.create(match_type="match", match_data="yes")],
            ),
        )
        child_instrument2 = factories.CollectionInstrumentFactory(id=3, collection_request__id=1)
        factories.ConditionFactory.create(
            instrument=instrument,
            data_getter=f"instrument:{child_instrument2.id}",
            condition_group=factories.ConditionGroupFactory.create(
                requirement_type="all-pass",
                cases=[factories.CaseFactory.create(match_type="match", match_data="yes")],
            ),
        )

        def test_conditions(*input_pairs):
            for id, data in input_pairs:
                models.CollectedInput.objects.filter(id=id).update(data=data)
            return instrument.test_conditions()

        factories.CollectedInputFactory.create(
            id=1, instrument__id=child_instrument1.id, data="dummy"
        )
        factories.CollectedInputFactory.create(
            id=2, instrument__id=child_instrument2.id, data="dummy"
        )
        self.assertEqual(test_conditions([1, "foo"], [2, "bar"]), False)
        self.assertEqual(test_conditions([1, "yes"], [2, "yes"]), True)
        self.assertEqual(test_conditions([1, "yes"], [2, "no"]), False)
        self.assertEqual(test_conditions([1, "no"], [2, "yes"]), False)
        self.assertEqual(test_conditions([1, "no"], [2, "no"]), False)

    def test_multiple_conditions_for_single_instrument_all_fail(self):
        """
        Verifies that multiple parent instruments are able to condtribute to the unlocking of a
        single dependent one.
        """

        instrument = factories.CollectionInstrumentFactory.create(
            id=1, collection_request__id=1, test_requirement_type="all-fail"
        )
        child_instrument1 = factories.CollectionInstrumentFactory(id=2, collection_request__id=1)
        factories.ConditionFactory.create(
            instrument=instrument,
            data_getter=f"instrument:{child_instrument1.id}",
            condition_group=factories.ConditionGroupFactory.create(
                requirement_type="all-pass",
                cases=[factories.CaseFactory.create(match_type="match", match_data="yes")],
            ),
        )
        child_instrument2 = factories.CollectionInstrumentFactory(id=3, collection_request__id=1)
        factories.ConditionFactory.create(
            instrument=instrument,
            data_getter=f"instrument:{child_instrument2.id}",
            condition_group=factories.ConditionGroupFactory.create(
                requirement_type="all-pass",
                cases=[factories.CaseFactory.create(match_type="match", match_data="yes")],
            ),
        )

        def test_conditions(*input_pairs):
            for id, data in input_pairs:
                models.CollectedInput.objects.filter(id=id).update(data=data)
            return instrument.test_conditions()

        factories.CollectedInputFactory.create(
            id=1, instrument__id=child_instrument1.id, data="dummy"
        )
        factories.CollectedInputFactory.create(
            id=2, instrument__id=child_instrument2.id, data="dummy"
        )
        self.assertEqual(test_conditions([1, "foo"], [2, "bar"]), True)
        self.assertEqual(test_conditions([1, "yes"], [2, "yes"]), False)
        self.assertEqual(test_conditions([1, "yes"], [2, "no"]), False)
        self.assertEqual(test_conditions([1, "no"], [2, "yes"]), False)
        self.assertEqual(test_conditions([1, "no"], [2, "no"]), True)
