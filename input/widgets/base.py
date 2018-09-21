__all__ = ['InputMethod']

__all__ = ['InputMethod', 'Widget']



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

    def clean(self, result):
        """ Clean the result and perform any necessary type coercion. """
        return result


class Widget(InputMethod):
    pass
