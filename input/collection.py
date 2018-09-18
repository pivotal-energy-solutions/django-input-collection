from django.forms.models import model_to_dict

from .models.utils import get_input_model

__all__ = ['Collector', 'store']


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


class Collector(object):
    __version__ = (0, 0, 0, 'dev')
    group = 'default'

    def __init__(self, collection_request, user=None, **kwargs):
        self.collection_request = collection_request
        self.user = user

        if 'group' in kwargs:
            self.group = kwargs['group']

    @property
    def info(self):
        """ Returns a JSON-safe spec for another tool to correctly supply inputs. """
        meta_info = self.get_meta()
        collection_request_info = model_to_dict(self.collection_request)
        instruments_info = self.get_instruments()

        info = {
            'meta': meta_info,
            'collection_request': collection_request_info,
            'group': self.group,
            'instruments': instruments_info,
        }
        return info

    def get_meta(self):
        return {
            'version': self.__version__,
        }

    def get_instruments(self):
        instruments_info = []

        queryset = self.collection_request.collectioninstrument_set.all()  # FIXME: valuesqueryset
        for instrument in queryset:
            info = model_to_dict(instrument)
            info['response_info'] = self.get_instrument_input_info(instrument)
            instruments_info.append(info)

        return instruments_info

    def get_instrument_input_info(self, instrument):
        """ Returns input specifications for data this instruments wants to collect. """
        policy_info = model_to_dict(instrument.response_policy)
        suggested_responses_info = self.get_suggested_responses_info(instrument)

        input_info = {
            'response_policy': policy_info,
            'suggested_responses': suggested_responses_info,
        }
        return input_info

    def get_suggested_responses_info(self, instrument):
        queryset = instrument.suggested_responses.all()
        suggested_responses_info = list(map(model_to_dict, queryset))
        return suggested_responses_info


class BaseAPICollector(Collector):
    def get_meta(self):
        meta_info = super(BaseAPICollector, self).get_meta()
        meta_info['api'] = self.get_api_info()
        return meta_info

    def get_api_info(self):
        return {}
