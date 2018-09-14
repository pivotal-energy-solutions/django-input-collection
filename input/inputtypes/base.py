from django.forms.models import model_to_dict

__all__ = ['Collector', 'InputMethod']


# _input_methods = set()
#
# def register(inputmethod_class):
#     _input_methods.add(inputmethod_class)


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
        info = {
            'meta': {
                'version': self.__version__,
            },
            'collection_request': model_to_dict(self.collection_request),
            'group': self.group,
        }
        return info


class InputMethod(object):
    """
    A stateless encapsulation of the components required to obtain and coerce data for an arbitrary
    CollectionInstrument.  Its job is to produce something that supports interaction through
    whatever external methodology is required to obtain data, and then to receive such data once
    that external methodology has complete.
    """

    def petition(self, instrument):
        raise NotImplemented

    def save(self, instrument, result):
        cleaned_result = self.validate(result)  # TODO: ValidationError workflow?
        # TODO: trigger creation of CollectedInput.  This must happen externally so that custom
        # model swaps can handle this as required.

    def validate(self, result):
        """ Validate the result and perform any necessary type coercion. """
        return result


# def interact(inputmethod, instrument):
#     if callable(inputmethod):
#         inputmethod = inputmethod()
#
#     result = inputmethod.petition(instrument)
#     inputmethod.recieve(instrument, result)
