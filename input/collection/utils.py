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


def test_condition_case(instrument, match_type, data=None, **context):
    """
    Tests a case described by ``match_type`` (and optional partial ``data`` helper) on a parent
    ``instrument``'s current inputs.
    """

    matcher = getattr(matchers, match_type.replace('-', '_'))

    input_data = list(instrument.collectedinput_set.filter_for_context(**context) \
                                .values_list('data', flat=True))

    status = matcher(input_data, match_data=data, instrument=instrument)

    return status


class CaseMatchers(object):
    def any(self, data, **kwargs):
        return bool(data)

    def none(self, data, **kwargs):
        return not data

    def all_suggested(self, data, match_data, instrument):
        if not len(data):
            return False
        if not isinstance(data, list):
            data = [data]
        suggested_data = instrument.suggested_responses.values_list('data', flat=True)
        all_suggested = set(data).issubset(set(suggested_data))
        return all_suggested

    def one_suggested(self, data, match_data, instrument):
        if not isinstance(data, list):
            data = [data]
        is_suggested = instrument.suggested_responses.filter(data__in=data).exists()
        return is_suggested

    def all_custom(self, data, match_data, instrument):
        if not len(data):
            return False
        if not isinstance(data, list):
            data = [data]
        suggested_data = list(instrument.suggested_responses.values_list('data', flat=True))
        overlaps = set(data).intersection(suggested_data)
        return len(overlaps) == 0

    def one_custom(self, data, match_data, instrument):
        if not isinstance(data, list):
            data = [data]
        is_not_suggested = (not instrument.suggested_responses.filter(data__in=data).exists())
        return is_not_suggested

    def match(self, data, match_data, **kwargs):
        return data == match_data

    def mismatch(self, data, match_data, **kwargs):
        return data != match_data

    def contains(self, data, match_data, **kwargs):
        return match_data in data

    def not_contains(self, data, match_data, **kwargs):
        return match_data not in data


matchers = CaseMatchers()
