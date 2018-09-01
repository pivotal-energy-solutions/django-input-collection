from .models.utils import get_input_model


def store(instrument, data, **create_kwargs):
    """
    Creates a new CollectedInput instance for the given data.  Any additional kwargs are sent to
    the manager's ``create()`` method, in case the CollectedInput model has been swapped and
    requires additional fields to successfully save.
    """
    CollectedInput = get_input_model()

    kwargs = {
        'collection_request': instrument.collection_request,
        'instrument': instrument,
        'data': data,
    }
    kwargs.update(create_kwargs)

    instance = CollectedInput.objects.create(**kwargs)

    return instance
