__all__ = ['replace_data_for_suggested_responses']


def replace_data_for_suggested_responses(instrument, *responses):
    """
    Maps any {'_suggested_response': pk} values to the actual data that the response represents.
    """

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

    if len(responses) == 1:
        return values[0]

    return values
