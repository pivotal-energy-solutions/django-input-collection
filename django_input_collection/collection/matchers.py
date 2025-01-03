try:
    from collections.abc import Iterable, Mapping
except ImportError:
    from collections import Iterable, Mapping

import logging
from itertools import chain

from ..apps import app

__all__ = ["test_condition_case", "matchers"]

log = logging.getLogger(__name__)

_should_log, log_method = app.get_verbose_logging


def test_condition_case(
    values, match_type, match_data=None, suggested_values=None, key_input=None, key_case=None
):
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
    return getattr(matchers, match_type.replace("-", "_"))


def list_wrap(data, wrap_strings=True, coerce_iterables=False):
    """
    Wraps ``data`` in a list if it is not inherantly iterable, or is a string or mapping.
    If ``wrap_strings`` is set to False, then strings will be left as-is.
    If ``coerce_iterables`` is True, then non-mapping iterables will be forced to a list type
    instead of being passed through.
    """
    is_string = isinstance(data, str)
    is_iterable = isinstance(data, Iterable)
    is_mapping = isinstance(data, Mapping)
    if is_iterable and not is_mapping and not is_string:
        if coerce_iterables:
            data = list(data)
    elif not is_string or wrap_strings:
        data = [data]
    return data


def eval_sample(match_data):
    try:
        return eval(match_data, {}, {})
    except Exception:
        return match_data


def coerce_type(match_data, value):
    _early_match = match_data
    _early_match_type = type(match_data)
    match_data = eval_sample(match_data)
    match_type = type(match_data)
    value_type = type(value)

    list_value_type = None
    if isinstance(value, (list, tuple, set)):
        _value_types = list(set([type(x) for x in value]))
        if len(_value_types) == 1:
            log.debug(f"Coercing list to {_value_types[0]}")
            list_value_type = _value_types[0]

    if _should_log:
        log_method(
            f"Match data: {match_data!r} match type: {match_type!r} value: {value!r} "
            f"value_type: {value_type} list value type: {list_value_type}, _early_match: "
            f"{_early_match} _early_match_type: {_early_match_type}"
        )

    if value is None or match_type == value_type or value_type in (list, tuple, set):
        if isinstance(match_data, (list, set, tuple)) and list_value_type is not None:
            return [list_value_type(x) for x in match_data]
        if list_value_type is not None and _early_match_type == list_value_type:
            return list_value_type(match_data)
        return match_data

    if isinstance(_early_match, str) and isinstance(list_value_type, str):
        return _early_match

    try:
        return value_type(match_data)
    except Exception as err:
        raise ValueError(
            f"Cannot convert sample match_data {match_data!r} ({match_type}) to "
            f"incoming {value} ({value_type}) - {err.__class__.__name__} - {err}"
        )


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
        has_suggested = not set(data).isdisjoint(set(suggested_values))
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
        match_data = list_wrap(coerce_type(match_data, data))
        match = set(list_wrap(data)) == set(match_data)
        if _should_log:
            log_method(f"match: {set(data)} {'=' if match else '!'}= {set(match_data)}")
        return match

    def mismatch(self, data, match_data, **kwargs):
        match_data = list_wrap(coerce_type(match_data, data))
        match = set(list_wrap(data)) != set(match_data)
        if _should_log:
            log_method(f"mismatch: {set(data)} {'=' if match else '!'}= {set(match_data)}")
        return match

    def greater_than(self, data, match_data, **kwargs):
        match_data = list_wrap(coerce_type(match_data, data))
        for d in list_wrap(data):
            if d is not None and any(d > candidate_match for candidate_match in match_data):
                if _should_log:
                    log.info(f"greater_than: {data} > {match_data}")
                return True
        if _should_log:
            log_method(f"greater_than: {data} !> {match_data}")
        return False

    def less_than(self, data, match_data, **kwargs):
        match_data = list_wrap(coerce_type(match_data, data))
        for d in list_wrap(data):
            if d is not None and any(d < candidate_match for candidate_match in match_data):
                if _should_log:
                    log.info(f"less_than: {data} < {match_data}")
                return True
        if _should_log:
            log_method(f"less_than: {data} !< {match_data}")
        return False

    def contains(self, data, match_data, **kwargs):
        data = list_wrap(data)
        match = any(
            map(lambda d: coerce_type(match_data, d) in list_wrap(d, wrap_strings=False), data)
        )
        if _should_log:
            log_method(f"contains: {match_data} {'' if match else 'not ' }contained in {data}")
        return match

    def not_contains(self, data, match_data, **kwargs):
        data = list_wrap(data)
        match = not any(
            map(lambda d: coerce_type(match_data, d) in list_wrap(d, wrap_strings=False), data)
        )
        if _should_log:
            log_method(f"not_contains: {match_data} {'' if match else 'not ' }contained in {data}")
        return match

    def one(self, data, match_data, **kwargs):
        evaled_sample = eval_sample(match_data)
        if isinstance(evaled_sample, int):
            evaled_sample = [evaled_sample]

        try:
            result = any(map(lambda d: d in evaled_sample, data))
        except TypeError:
            log_method(f"one TypeError found data = {data!r} evaled_sample = {evaled_sample!r}")
            result = False

        if _should_log:
            log_method(f"one: {data} {'' if result else 'not '}in {match_data}")
        return result

    def zero(self, data, match_data, **kwargs):
        evaled_sample = eval_sample(match_data)
        if isinstance(evaled_sample, int):
            evaled_sample = [evaled_sample]

        try:
            result = not any(map(lambda d: d in evaled_sample, data))
        except TypeError:
            log_method(f"zero TypeError found data = {data!r} evaled_sample = {evaled_sample!r}")
            result = False

        if _should_log:
            log_method(f"zero: {data} {'' if result else 'not '}in {match_data}")
        return result


matchers = CaseMatchers()
