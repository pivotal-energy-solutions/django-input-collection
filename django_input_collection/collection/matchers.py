import collections
from itertools import chain

import six

__all__ = ['test_condition_case', 'matchers']


def test_condition_case(values, match_type, match_data=None,
                        suggested_values=None, key_input=None, key_case=None):
    """
    Routes a ``match_type`` condition to the appropriate test function, given an instrument's active
    inputs (filtered by **context kwargs) or a list of raw values representing the same. If
    ``match_type`` requires the an outside data helper (such as the 'contains' test), it must be
    supplied here as ``data`` (the name of the field on the a Case model).
                        
    Match types relying on the distinction between suggested and custom values will expect the
    ``suggested_values`` kwarg to be given, or else will be treated as an empty list and likely
    produce unexpected behavior.

    If either the instrument/raw data or the suggested/match data requires coercion before the test
    is applied, the ``key_input`` and ``key_case`` kwargs (respectively) can be set to mapping
    functions for that purpose.
    """

    if suggested_values is None:
        suggested_values = []

    values = list_wrap(values, coerce_iterables=True)

    if key_input is not None:
        values = list(map(key_input, values))
    if key_case is not None:
        suggested_values = list(map(key_case, suggested_values))
        if match_data is not None:
            match_data = key_case(match_data)

    # Flatten nested values that came in as a list from a single response (i.e., multiple=True)
    values = list(chain(*[list_wrap(item) for item in values]))
    matcher = resolve_matcher(match_type)
    status = matcher(values, suggested_values=suggested_values, match_data=match_data)

    return status


def resolve_matcher(match_type):
    return getattr(matchers, match_type.replace('-', '_'))


def list_wrap(data, wrap_strings=True, coerce_iterables=False):
    """
    Wraps ``data`` in a list if it is not inherantly iterable, or is a string or mapping.
    If ``wrap_strings`` is set to False, then strings will be left as-is.
    If ``coerce_iterables`` is True, then non-mapping iterables will be forced to a list type
    instead of being passed through.
    """
    is_string = isinstance(data, six.string_types)
    is_iterable = isinstance(data, collections.Iterable)
    is_mapping = isinstance(data, collections.Mapping)
    if is_iterable and not is_mapping and not is_string:
        if coerce_iterables:
            data = list(data)
    elif not is_string or wrap_strings:
        data = [data]
    return data


def eval_sample(match_data):
    try:
        return eval(match_data, {}, {})
    except:
        return match_data


def coerce_type(match_data, value):
    match_data = eval_sample(match_data)
    match_type = type(match_data)
    value_type = type(value)
    if match_type == value_type or value_type in (list, tuple, set):
        return match_data

    try:
        return value_type(match_data)
    except:
        raise ValueError('Cannot convert sample match_data %r (%r) to incoming %r (%r)' % (
            match_data, match_type, value, value_type,
        ))


class CaseMatchers(object):
    def any(self, data, **kwargs):
        data = list_wrap(data)
        return any(data)

    def none(self, data, **kwargs):
        data = list_wrap(data)
        return not any(data)

    def all_suggested(self, data, suggested_values, **kwargs):
        if not len(data):
            return False
        data = list_wrap(data)
        all_suggested = set(data).issubset(set(suggested_values))
        return all_suggested

    def one_suggested(self, data, suggested_values, **kwargs):
        data = list_wrap(data)
        has_suggested = (not set(data).isdisjoint(set(suggested_values)))
        return has_suggested

    def all_custom(self, data, suggested_values, **kwargs):
        if not len(data):
            return False
        data = list_wrap(data)
        overlaps = set(data).intersection(set(suggested_values))
        return len(overlaps) == 0

    def one_custom(self, data, suggested_values, **kwargs):
        data = list_wrap(data)
        overlaps = set(data).difference(set(suggested_values))
        return len(overlaps) > 0

    def match(self, data, match_data, **kwargs):
        return list_wrap(data) == list_wrap(coerce_type(match_data, data))

    def mismatch(self, data, match_data, **kwargs):
        return list_wrap(data) != list_wrap(coerce_type(match_data, data))

    def greater_than(self, data, match_data, **kwargs):
        data = list_wrap(data)
        if len(data) == 1:
            data = data[0]
        return list_wrap(data) > list_wrap(coerce_type(match_data, data))
        
    def less_than(self, data, match_data, **kwargs):
        data = list_wrap(data)
        if len(data) == 1:
            data = data[0]
        return list_wrap(data) < list_wrap(coerce_type(match_data, data))
        
    def contains(self, data, match_data, **kwargs):
        data = list_wrap(data)
        return any(map(lambda d: coerce_type(match_data, d) in list_wrap(d, wrap_strings=False), data))

    def not_contains(self, data, match_data, **kwargs):
        data = list_wrap(data)
        return not any(map(lambda d: coerce_type(match_data, d) in list_wrap(d, wrap_strings=False), data))

    def one(self, data, match_data, **kwargs):
        data = list_wrap(data)
        return any(map(lambda d: d in eval_sample(match_data), data))

    def zero(self, data, match_data, **kwargs):
        data = list_wrap(data)
        return not any(map(lambda d: d in eval_sample(match_data), data))


matchers = CaseMatchers()
