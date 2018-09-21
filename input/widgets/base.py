from collections import UserDict

__all__ = ['InputMethod', 'Widget']


class missing(object):
    pass


class InputMethod(UserDict):
    """
    A stateless encapsulation of the components required to obtain and coerce data for an arbitrary
    CollectionInstrument.  Its job is to produce something that supports interaction through
    whatever external methodology is required to obtain data, and then to receive such data once
    that external methodology has complete.
    """

    def __init__(self, **kwargs):
        super(InputMethod, self).__init__(**kwargs)
        self.update_kwargs(**kwargs)

    def __getattr__(self, k):
        if k == 'data':
            return self.data

        return self.data[k]

    def __setattr__(self, k, v):
        super(InputMethod, self).__setattr__(k, v)

        if k == 'data':
            return

        self.data[k] = v

    def update_kwargs(self, **kwargs):
        for k, v in kwargs.items():
            attr = getattr(self, k, missing)
            if attr is missing or k.startswith('_') or callable(attr):
                raise AttributeError("Invalid attribute %r for widget %r" % (k, self))
            setattr(self, k, v)

    def clean(self, result):
        """ Clean the result and perform any necessary type coercion. """
        return result


class Widget(InputMethod):
    pass
