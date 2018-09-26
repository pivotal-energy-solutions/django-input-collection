import collections

from django.db.models import Model

__all__ = ['get_data_for_suggested_responses', 'test_condition_case']


def get_data_for_suggested_responses(instrument, *responses):
    class missing:
        pass

    values = []

    lookups = dict(instrument.suggested_responses.values_list('id', 'data'))
    for response in responses:
        data = response  # Assume raw passthrough by default

        # Transform data referring to a SuggestedResponse id
        if isinstance(data, dict):
            suggested_response_id = data.get('_suggested_response', missing)
            if suggested_response_id is not missing:
                try:
                    suggested_response_id = int(suggested_response_id)
                except ValueError as e:
                    pass  # It's going to raise again shortly anyway with a better message

                # Verify the coded SuggestedResponse id is valid for this instrument
                data = lookups.get(suggested_response_id, missing)
                if data is missing:
                    raise ValueError("[CollectionInstrument id=%r] Invalid SuggestedResponse id=%r in choices: %r" % (
                        instrument.id,
                        suggested_response_id,
                        lookups,
                    ))

        values.append(data)

    return values


def test_condition_case(instrument_or_raw_values, match_type, match_data=None,
                        suggested_values=None, **context):
    """
    Routes a ``match_type`` condition to the appropriate test function, given an instrument's active
    inputs (filtered by **context kwargs) or a list of raw values representing the same. If
    ``match_type`` requires the an outside data helper (such as the 'contains' test), it must be
    supplied here as ``data`` (the name of the field on the a Case model).
                        
    If an instrument is given, its suggested response values will be fetch automatically for
    applicable match scenarios (requiring additional ``**context`` kwargs to correctly filter for
    context), however an override list can be provided via ``suggested_values``.

    If a list of raw values is given instead of an instrument reference, match types relying on the
    distinction between suggested and custom values will expect the ``suggested_values`` kwarg to
    be given, or else will be treated as an empty list and likely produce unexpected behavior.
    """

    if isinstance(instrument_or_raw_values, Model):
        instrument = instrument_or_raw_values
        values = list(instrument.collectedinput_set.filter_for_context(**context) \
                                .values_list('data', flat=True))
        if not suggested_values:
            # Avoid list coercion at this step so that tests not requiring this query won't ever
            # end up hitting the database.
            suggested_values = instrument.suggested_responses.values_list('data', flat=True)
    else:
        values = instrument_or_raw_values
        if isinstance(values, str) or not isinstance(values, collections.Iterable):
            values = [values]
        else:
            values = list(values)
        suggested_values = suggested_values or []

    matcher = matchers.resolve(match_type)
    status = matcher(values, suggested_values=suggested_values, match_data=match_data)

    return status


class CaseMatchers(object):
    def resolve(self, match_type):
        return getattr(self, match_type.replace('-', '_'))

    def any(self, data, **kwargs):
        if not isinstance(data, list):
            data = [data]
        return any(data)

    def none(self, data, **kwargs):
        if not isinstance(data, list):
            data = [data]
        return not any(data)

    def all_suggested(self, data, suggested_values, **kwargs):
        if not len(data):
            return False
        if not isinstance(data, list):
            data = [data]
        all_suggested = set(data).issubset(set(suggested_values))
        return all_suggested

    def one_suggested(self, data, suggested_values, **kwargs):
        if not isinstance(data, list):
            data = [data]
        has_suggested = (not set(data).isdisjoint(set(suggested_values)))
        return has_suggested

    def all_custom(self, data, suggested_values, **kwargs):
        if not len(data):
            return False
        if not isinstance(data, list):
            data = [data]
        overlaps = set(data).intersection(set(suggested_values))
        return len(overlaps) == 0

    def one_custom(self, data, suggested_values, **kwargs):
        if not isinstance(data, list):
            data = [data]
        overlaps = set(data).difference(set(suggested_values))
        return len(overlaps) > 0

    def match(self, data, match_data, **kwargs):
        return data == match_data

    def mismatch(self, data, match_data, **kwargs):
        return data != match_data

    def contains(self, data, match_data, **kwargs):
        return match_data in data

    def not_contains(self, data, match_data, **kwargs):
        return match_data not in data


matchers = CaseMatchers()
