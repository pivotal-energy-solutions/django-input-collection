def expand_suggested_responses(instrument, lookups, *responses):
    """
    Maps any {'_suggested_response': pk} values to the SuggestedResponse by that id, as long as it
    is present in the ``lookups`` dict.
    """
    data_lookups = {bound_response.data: bound_response for bound_response in lookups.values()}

    values = []
    for response in responses:
        data = None
        bound_response_id = None

        # Transform data referring to a SuggestedResponse into that instance directly
        if isinstance(response, dict):
            bound_response_id = response.get('_suggested_response')
            if bound_response_id in lookups:
                data = lookups[bound_response_id]
        elif response in data_lookups:
            data = data_lookups[response]

        if data is None:
            raise ValueError("[CollectionInstrument id=%r] Invalid bound response=%r in choices: %r" % (
                instrument.id,
                bound_response_id or response,
                lookups if bound_response_id else data_lookups,
            ))

        values.append(data)

    if len(responses) == 1:
        return values[0]

    return values
