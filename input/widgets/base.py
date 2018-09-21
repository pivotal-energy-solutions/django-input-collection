__all__ = ['InputMethod']


# _input_methods = set()
#
# def register(inputmethod_class):
#     _input_methods.add(inputmethod_class)


class InputMethod(object):
    """
    A stateless encapsulation of the components required to obtain and coerce data for an arbitrary
    CollectionInstrument.  Its job is to produce something that supports interaction through
    whatever external methodology is required to obtain data, and then to receive such data once
    that external methodology has complete.
    """

    def __init__(self, **kwargs):
        self.update_kwargs(**kwargs)

    def update_kwargs(self, **kwargs):
        for k, v in kwargs.items():
            if not hasattr(self, k):
                raise AttributeError("Invalid attribute %r for widget %r" % (k, self))
            setattr(self, k, v)

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
