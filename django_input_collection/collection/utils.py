def expand_suggested_responses(instrument, lookups, *responses):
    """
    Maps any {'_suggested_response': pk} values to the SuggestedResponse by that id, as long as it
    is present in the ``lookups`` dict.
    """

    values = []
    for response in responses:
        data = response  # Assume raw passthrough by default

        # Transform data referring to a SuggestedResponse into that instance directly
        if isinstance(data, dict) and '_suggested_response' in data:
            bound_response_id = data['_suggested_response']
            if bound_response_id in lookups:
                data = lookups[bound_response_id]
            else:
                raise ValueError("[CollectionInstrument id=%r] Invalid bound response id=%r in choices: %r" % (
                    instrument.id,
                    bound_response_id,
                    lookups,
                ))

        values.append(data)

    if len(responses) == 1:
        return values[0]

    return values
