from django.test import TestCase

from .. import models
from ..collection.utils import test_condition_case, matchers, resolve_matcher
from . import factories


CollectedInput = models.get_input_model()


class TestCoreMatcher(TestCase):
    """ Verifies behavior of the underlying ``collection.utils.test_condition_case`` function. """

    def test_matcher_resolver(self):
        self.assertEqual(resolve_matcher('all-custom'), matchers.all_custom)
        self.assertEqual(resolve_matcher('all_custom'), matchers.all_custom)

    def test_matcher_errors_on_bad_match_type(self):
        with self.assertRaises(AttributeError):
            resolve_matcher('foo')

        with self.assertRaises(AttributeError):
            test_condition_case('data', match_type='foo')

    def test_matcher_accepts_bare_input(self):
        """ Verifies that a single data input arg is cast to a list. """
        self.assertEqual(test_condition_case('a', match_type='all-suggested', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(test_condition_case('a', match_type='one-suggested', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(test_condition_case('a', match_type='all-custom', suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(test_condition_case('a', match_type='one-custom', suggested_values=['a', 'b', 'c']), False)

    def test_matcher_accepts_list_input(self):
        """ Verifies that a data list input arg is taken as it is. """
        self.assertEqual(test_condition_case(['a'], match_type='all-suggested', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(test_condition_case(['a'], match_type='one-suggested', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(test_condition_case(['a'], match_type='all-custom', suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(test_condition_case(['a'], match_type='one-custom', suggested_values=['a', 'b', 'c']), False)

    def test_matcher_accepts_valuesqueryset_input(self):
        """ Verifies that a data list input arg is taken as it is. """
        factories.CollectedInputFactory.create(**{
            'data': 'a',
        })
        valueslist = CollectedInput.objects.values_list('data', flat=True)

        self.assertEqual(test_condition_case(valueslist, match_type='all-suggested', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(test_condition_case(valueslist, match_type='one-suggested', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(test_condition_case(valueslist, match_type='all-custom', suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(test_condition_case(valueslist, match_type='one-custom', suggested_values=['a', 'b', 'c']), False)

    def test_matcher_applies_context_to_instrument_collectedinput_queryset(self):
        """
        Verifies that a CollectionInstrument with associated SuggestedResponses forwards those
        suggested response values to the matcher.
        """
        a = factories.SuggestedResponseFactory.create(data='a')
        b = factories.SuggestedResponseFactory.create(data='b')
        c = factories.SuggestedResponseFactory.create(data='c')
        instrument = factories.CollectionInstrumentFactory.create(**{
            'suggested_responses': [a, b, c],
        })
        factories.CollectedInputFactory.create(**{
            'instrument': instrument,
            'data': a.data,
        })

        self.assertEqual(test_condition_case(instrument, 'one-suggested', data='a'), True)
        self.assertEqual(test_condition_case(instrument, 'one-suggested', data='b'), False)

    def test_matcher_reads_instrument_suggested_responses(self):
        """
        Verifies that a CollectionInstrument with associated SuggestedResponses forwards those
        suggested response values to the matcher.
        """
        a = factories.SuggestedResponseFactory.create(data='a')
        b = factories.SuggestedResponseFactory.create(data='b')
        c = factories.SuggestedResponseFactory.create(data='c')
        instrument = factories.CollectionInstrumentFactory.create(**{
            'suggested_responses': [a, b, c],
        })
        factories.CollectedInputFactory.create(**{
            'instrument': instrument,
            'data': a.data,
        })

        self.assertEqual(test_condition_case(instrument, 'one-suggested'), True)

    def test_matcher_overrides_instrument_suggested_responses_with_suggested_values(self):
        """
        Verifies that a CollectionInstrument with associated SuggestedResponses forwards those
        suggested response values to the matcher.
        """
        a = factories.SuggestedResponseFactory.create(data='a')
        b = factories.SuggestedResponseFactory.create(data='b')
        c = factories.SuggestedResponseFactory.create(data='c')
        instrument = factories.CollectionInstrumentFactory.create(**{
            'suggested_responses': [a, b, c],
        })
        factories.CollectedInputFactory.create(**{
            'instrument': instrument,
            'data': a.data,
        })

        self.assertEqual(test_condition_case(instrument, 'one-suggested', suggested_values=['OVERRIDDEN']), False)


class TestMatchTypes(TestCase):
    """ Verifies behavior of the individual matchers. """
    def test_match_type_any(self):
        self.assertEqual(matchers.any('foo'), True)
        self.assertEqual(matchers.any(['foo']), True)
        self.assertEqual(matchers.any(['foo', 'bar']), True)
        self.assertEqual(matchers.any(None), False)
        self.assertEqual(matchers.any([]), False)
        self.assertEqual(matchers.any(''), False)
        self.assertEqual(matchers.any(['']), False)

    def test_match_type_none(self):
        self.assertEqual(matchers.none('foo'), False)
        self.assertEqual(matchers.none(['foo']), False)
        self.assertEqual(matchers.none(['foo', 'bar']), False)
        self.assertEqual(matchers.none(None), True)
        self.assertEqual(matchers.none(''), True)
        self.assertEqual(matchers.none([]), True)
        self.assertEqual(matchers.none(['']), True)

    def test_match_type_all_suggested(self):
        self.assertEqual(matchers.all_suggested('a', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.all_suggested(['a'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.all_suggested(['a', 'b'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.all_suggested(['a', 'b', 'c'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.all_suggested(['a', 'b', 'c', 'd'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.all_suggested('d', suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.all_suggested(['d'], suggested_values=['a', 'b', 'c']), False)

    def test_match_type_one_suggested(self):
        self.assertEqual(matchers.one_suggested('a', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.one_suggested(['a'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.one_suggested(['a', 'b'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.one_suggested(['a', 'b', 'c'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.one_suggested(['a', 'b', 'c', 'd'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.one_suggested('d', suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.one_suggested(['d'], suggested_values=['a', 'b', 'c']), False)

    def test_match_type_all_custom(self):
        self.assertEqual(matchers.all_custom('a', suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.all_custom(['a'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.all_custom(['a', 'b'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.all_custom(['a', 'b', 'c'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.all_custom(['a', 'b', 'c', 'd'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.all_custom('d', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.all_custom(['d'], suggested_values=['a', 'b', 'c']), True)

    def test_match_type_one_custom(self):
        self.assertEqual(matchers.one_custom('a', suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.one_custom(['a'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.one_custom(['a', 'b'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.one_custom(['a', 'b', 'c'], suggested_values=['a', 'b', 'c']), False)
        self.assertEqual(matchers.one_custom(['a', 'b', 'c', 'd'], suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.one_custom('d', suggested_values=['a', 'b', 'c']), True)
        self.assertEqual(matchers.one_custom(['d'], suggested_values=['a', 'b', 'c']), True)

    def test_match_type_match(self):
        self.assertEqual(matchers.match('foo', match_data='foo'), True)
        self.assertEqual(matchers.match('foo', match_data='Foo'), False)
        self.assertEqual(matchers.match('foo', match_data='xfoox'), False)
        self.assertEqual(matchers.match('foo', match_data='bar'), False)
        self.assertEqual(matchers.match('foo', match_data='Bar'), False)
        self.assertEqual(matchers.match('foo', match_data='xbarx'), False)
        self.assertEqual(matchers.match(['foo'], match_data='foo'), False)

    def test_match_type_mismatch(self):
        self.assertEqual(matchers.mismatch('foo', match_data='foo'), False)
        self.assertEqual(matchers.mismatch('foo', match_data='Foo'), True)
        self.assertEqual(matchers.mismatch('foo', match_data='xfoox'), True)
        self.assertEqual(matchers.mismatch('foo', match_data='bar'), True)
        self.assertEqual(matchers.mismatch('foo', match_data='Bar'), True)
        self.assertEqual(matchers.mismatch('foo', match_data='xbarx'), True)
        self.assertEqual(matchers.mismatch(['foo'], match_data='foo'), True)

    def test_match_type_contains(self):
        self.assertEqual(matchers.contains('foo', match_data='foo'), True)
        self.assertEqual(matchers.contains('foo', match_data='Foo'), False)
        self.assertEqual(matchers.contains('foo', match_data='xfoox'), False)
        self.assertEqual(matchers.contains('foo', match_data='bar'), False)
        self.assertEqual(matchers.contains('foo', match_data='Bar'), False)
        self.assertEqual(matchers.contains('foo', match_data='xbarx'), False)

        self.assertEqual(matchers.contains('xfooxbarx', match_data='foo'), True)
        self.assertEqual(matchers.contains('xfooxbarx', match_data='Foo'), False)
        self.assertEqual(matchers.contains('xfooxbarx', match_data='xfoox'), True)
        self.assertEqual(matchers.contains('xfooxbarx', match_data='bar'), True)
        self.assertEqual(matchers.contains('xfooxbarx', match_data='Bar'), False)
        self.assertEqual(matchers.contains('xfooxbarx', match_data='xbarx'), True)
        self.assertEqual(matchers.contains(['xfooxbarx'], match_data='foo'), True)

    def test_match_type_not_contains(self):
        self.assertEqual(matchers.not_contains('foo', match_data='foo'), False)
        self.assertEqual(matchers.not_contains('foo', match_data='Foo'), True)
        self.assertEqual(matchers.not_contains('foo', match_data='xfoox'), True)
        self.assertEqual(matchers.not_contains('foo', match_data='bar'), True)
        self.assertEqual(matchers.not_contains('foo', match_data='Bar'), True)
        self.assertEqual(matchers.not_contains('foo', match_data='xbarx'), True)

        self.assertEqual(matchers.not_contains('xfooxbarx', match_data='foo'), False)
        self.assertEqual(matchers.not_contains('xfooxbarx', match_data='Foo'), True)
        self.assertEqual(matchers.not_contains('xfooxbarx', match_data='xfoox'), False)
        self.assertEqual(matchers.not_contains('xfooxbarx', match_data='bar'), False)
        self.assertEqual(matchers.not_contains('xfooxbarx', match_data='Bar'), True)
        self.assertEqual(matchers.not_contains('xfooxbarx', match_data='xbarx'), False)
        self.assertEqual(matchers.not_contains(['xfooxbarx'], match_data='foo'), False)


class TestSingleConditionGroupRequirementTypes(TestCase):
    def test_group_cases_requirement_type_all_pass(self):
        """ Verifies the AND requirement for a group with a pair of cases. """
        group = factories.ConditionGroupFactory.create(**{
            'requirement_type': 'all-pass',
            'cases': [
                # A non-suggested response
                factories.CaseFactory.create(match_type='all-custom'),

                # That also contains 'foo'
                factories.CaseFactory.create(match_type='contains', match_data='foo'),
            ],
        })

        self.assertEqual(group.test('a'), False)
        self.assertEqual(group.test('foo'), True)
        self.assertEqual(group.test('xfoox'), True)
        self.assertEqual(group.test('bar'), False)
        self.assertEqual(group.test(['foo', 'bar']), True)
        self.assertEqual(group.test(['bar']), False)
        self.assertEqual(group.test(['xfoox']), True)

        self.assertEqual(group.test('foo', suggested_values=['foo']), False)
        self.assertEqual(group.test('xfoox', suggested_values=['foo']), True)
        self.assertEqual(group.test(['foo', 'xfoox'], suggested_values=['foo']), False)

        self.assertEqual(group.test('bar', suggested_values=['bar']), False)
        self.assertEqual(group.test('xbarx', suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xbarx'], suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xfoox'], suggested_values=['bar']), False)

    def test_group_cases_requirement_type_one_pass(self):
        """ Verifies the OR requirement for a group with a pair of cases. """
        group = factories.ConditionGroupFactory.create(**{
            'requirement_type': 'one-pass',
            'cases': [
                # A non-suggested response
                factories.CaseFactory.create(match_type='all-custom'),

                # Or a suggested response that contains 'foo'
                factories.CaseFactory.create(match_type='contains', match_data='foo'),
            ],
        })

        self.assertEqual(group.test('a'), True)
        self.assertEqual(group.test('foo'), True)
        self.assertEqual(group.test('xfoox'), True)
        self.assertEqual(group.test('bar'), True)
        self.assertEqual(group.test(['foo', 'bar']), True)
        self.assertEqual(group.test(['bar']), True)
        self.assertEqual(group.test(['xfoox']), True)

        self.assertEqual(group.test('foo', suggested_values=['foo']), True)
        self.assertEqual(group.test('xfoox', suggested_values=['foo']), True)
        self.assertEqual(group.test(['foo', 'xfoox'], suggested_values=['foo']), True)

        self.assertEqual(group.test('bar', suggested_values=['bar']), False)
        self.assertEqual(group.test('xbarx', suggested_values=['bar']), True)
        self.assertEqual(group.test(['bar', 'xbarx'], suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xfoox'], suggested_values=['bar']), True)

    def test_group_cases_requirement_type_all_fail(self):
        """ Verifies the NONE requirement for a group with a pair of cases. """
        group = factories.ConditionGroupFactory.create(**{
            'requirement_type': 'all-fail',
            'cases': [
                # A non-custom response (synonymous with 'all-suggested', once we invert)
                factories.CaseFactory.create(match_type='all-custom'),

                # That doesn't contain 'foo' (synonymous with 'not-contains', once we invert)
                factories.CaseFactory.create(match_type='contains', match_data='foo'),
            ],
        })

        self.assertEqual(group.test('a'), False)
        self.assertEqual(group.test('foo'), False)
        self.assertEqual(group.test('xfoox'), False)
        self.assertEqual(group.test('bar'), False)
        self.assertEqual(group.test(['foo', 'bar']), False)
        self.assertEqual(group.test(['bar']), False)
        self.assertEqual(group.test(['xfoox']), False)

        self.assertEqual(group.test('foo', suggested_values=['foo']), False)
        self.assertEqual(group.test('xfoox', suggested_values=['foo']), False)
        self.assertEqual(group.test(['foo', 'xfoox'], suggested_values=['foo']), False)

        self.assertEqual(group.test('bar', suggested_values=['bar']), True)
        self.assertEqual(group.test('xbarx', suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xbarx'], suggested_values=['bar']), True)
        self.assertEqual(group.test(['bar', 'xfoox'], suggested_values=['bar']), False)


class TestStackedConditionGroupRequirementTypes(TestCase):
    def test_group_child_groups_requirement_type_all_pass(self):
        """ Verifies the AND requirement for a group with subgroups. """
        group = factories.ConditionGroupFactory.create(**{
            'requirement_type': 'all-pass',
            'child_groups': [
                factories.ConditionGroupFactory.create(**{
                    'requirement_type': 'all-pass',
                    'cases': [
                        # A non-suggested response
                        factories.CaseFactory.create(match_type='all-custom'),
                    ],
                }),
                factories.ConditionGroupFactory.create(**{
                    'requirement_type': 'all-pass',
                    'cases': [
                        # That also contains 'foo'
                        factories.CaseFactory.create(match_type='contains', match_data='foo'),
                    ],
                }),
            ],
        })

        self.assertEqual(group.test('a'), False)
        self.assertEqual(group.test('foo'), True)
        self.assertEqual(group.test('xfoox'), True)
        self.assertEqual(group.test('bar'), False)
        self.assertEqual(group.test(['foo', 'bar']), True)
        self.assertEqual(group.test(['bar']), False)
        self.assertEqual(group.test(['xfoox']), True)

        self.assertEqual(group.test('foo', suggested_values=['foo']), False)
        self.assertEqual(group.test('xfoox', suggested_values=['foo']), True)
        self.assertEqual(group.test(['foo', 'xfoox'], suggested_values=['foo']), False)

        self.assertEqual(group.test('bar', suggested_values=['bar']), False)
        self.assertEqual(group.test('xbarx', suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xbarx'], suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xfoox'], suggested_values=['bar']), False)

    def test_group_cases_requirement_type_one_pass(self):
        """ Verifies the OR requirement for a group with subgroups. """
        group = factories.ConditionGroupFactory.create(**{
            'requirement_type': 'one-pass',
            'child_groups': [
                factories.ConditionGroupFactory.create(**{
                    'requirement_type': 'all-pass',
                    'cases': [
                        # A non-suggested response
                        factories.CaseFactory.create(match_type='all-custom'),
                    ],
                }),
                factories.ConditionGroupFactory.create(**{
                    'requirement_type': 'all-pass',
                    'cases': [
                        # Or a suggested response that contains 'foo'
                        factories.CaseFactory.create(match_type='contains', match_data='foo'),
                    ],
                }),
            ],
        })

        self.assertEqual(group.test('a'), True)
        self.assertEqual(group.test('foo'), True)
        self.assertEqual(group.test('xfoox'), True)
        self.assertEqual(group.test('bar'), True)
        self.assertEqual(group.test(['foo', 'bar']), True)
        self.assertEqual(group.test(['bar']), True)
        self.assertEqual(group.test(['xfoox']), True)

        self.assertEqual(group.test('foo', suggested_values=['foo']), True)
        self.assertEqual(group.test('xfoox', suggested_values=['foo']), True)
        self.assertEqual(group.test(['foo', 'xfoox'], suggested_values=['foo']), True)

        self.assertEqual(group.test('bar', suggested_values=['bar']), False)
        self.assertEqual(group.test('xbarx', suggested_values=['bar']), True)
        self.assertEqual(group.test(['bar', 'xbarx'], suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xfoox'], suggested_values=['bar']), True)

    def test_group_cases_requirement_type_all_fail(self):
        """ Verifies the NONE requirement for a group with subgroups. """
        group = factories.ConditionGroupFactory.create(**{
            'requirement_type': 'all-fail',
            'child_groups': [
                factories.ConditionGroupFactory.create(**{
                    'requirement_type': 'all-pass',
                    'cases': [
                        # A non-custom response (synonymous with 'all-suggested', once we invert)
                        factories.CaseFactory.create(match_type='all-custom'),
                    ],
                }),
                factories.ConditionGroupFactory.create(**{
                    'requirement_type': 'all-pass',
                    'cases': [
                        # That doesn't contain 'foo' (synonymous with 'not-contains', once we
                        # invert)
                        factories.CaseFactory.create(match_type='contains', match_data='foo'),
                    ],
                }),
            ],
        })

        self.assertEqual(group.test('a'), False)
        self.assertEqual(group.test('foo'), False)
        self.assertEqual(group.test('xfoox'), False)
        self.assertEqual(group.test('bar'), False)
        self.assertEqual(group.test(['foo', 'bar']), False)
        self.assertEqual(group.test(['bar']), False)
        self.assertEqual(group.test(['xfoox']), False)

        self.assertEqual(group.test('foo', suggested_values=['foo']), False)
        self.assertEqual(group.test('xfoox', suggested_values=['foo']), False)
        self.assertEqual(group.test(['foo', 'xfoox'], suggested_values=['foo']), False)

        self.assertEqual(group.test('bar', suggested_values=['bar']), True)
        self.assertEqual(group.test('xbarx', suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xbarx'], suggested_values=['bar']), True)
        self.assertEqual(group.test(['bar', 'xfoox'], suggested_values=['bar']), False)

    def test_group_assesses_subgroups_and_local_cases(self):
        group = factories.ConditionGroupFactory.create(**{
            'requirement_type': 'all-pass',
            'cases': [
                # A non-suggested response
                factories.CaseFactory.create(match_type='all-custom'),
            ],
            'child_groups': [
                factories.ConditionGroupFactory.create(**{
                    'requirement_type': 'all-pass',
                    'cases': [
                        # That also contains 'foo'
                        factories.CaseFactory.create(match_type='contains', match_data='foo'),
                    ],
                }),
            ],
        })

        self.assertEqual(group.test('a'), False)
        self.assertEqual(group.test('foo'), True)
        self.assertEqual(group.test('xfoox'), True)
        self.assertEqual(group.test('bar'), False)
        self.assertEqual(group.test(['foo', 'bar']), True)
        self.assertEqual(group.test(['bar']), False)
        self.assertEqual(group.test(['xfoox']), True)

        self.assertEqual(group.test('foo', suggested_values=['foo']), False)
        self.assertEqual(group.test('xfoox', suggested_values=['foo']), True)
        self.assertEqual(group.test(['foo', 'xfoox'], suggested_values=['foo']), False)

        self.assertEqual(group.test('bar', suggested_values=['bar']), False)
        self.assertEqual(group.test('xbarx', suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xbarx'], suggested_values=['bar']), False)
        self.assertEqual(group.test(['bar', 'xfoox'], suggested_values=['bar']), False)
