from input.tests import factories

suggested_responses = [
    factories.SuggestedResponseFactory.create(data='Yes'),
    factories.SuggestedResponseFactory.create(data='No'),
    factories.SuggestedResponseFactory.create(data='Maybe'),
]

factories.CollectedInputFactory.create_batch(size=10, **{
    'collection_request__id': 1,
    'instrument__suggested_responses': suggested_responses,
})
