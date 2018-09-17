from .models.utils import get_input_model


def store(instrument, data, instance=None, **model_kwargs):
    """
    Creates a new CollectedInput instance for the given data.  Any additional kwargs are sent to
    the manager's ``create()`` method, in case the CollectedInput model has been swapped and
    requires additional fields to successfully save.
    """
    CollectedInput = get_input_model()

    db_data = CollectedInput().serialize_data(data)  # FIXME: classmethod/staticmethod?

    kwargs = {
        'instrument': instrument,
        'data': db_data,

        # Disallow data integrity funnybusiness
        'collection_request': instrument.collection_request,
    }
    kwargs.update(model_kwargs)

    pk = None
    if instance is not None:
        pk = instance.pk
    instance, created = CollectedInput.objects.update_or_create(pk=pk, defaults=kwargs)

    return instance
