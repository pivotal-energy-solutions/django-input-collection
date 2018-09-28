from collections import UserDict
from functools import reduce

__all__ = ['InputMethod']


def flatten_dicts(*args, **kwargs):
    return reduce(lambda d, d2: dict(d, **d2), args + (kwargs,), {})


def filter_safe_dict(data, attrs=None):
    """
    Returns current names and values for valid writeable attributes. If ``attrs`` is given, then
    the returned dict will contain only items named in that iterable.
    """
    return {k: v for k, v in data.items() if all((
        not k.startswith('_'),
        not callable(v) and not isinstance(v, (classmethod, staticmethod)),
        not attrs or (k in attrs),
    ))}


class InputMethod(UserDict):
    """
    A stateless encapsulation of the components required to obtain and coerce data for an arbitrary
    CollectionInstrument.  Its job is to produce something that supports interaction through
    whatever external methodology is required to obtain data, and then to receive such data once
    that external methodology has complete.
    """

    def __init__(self, *args, _raise=True, **kwargs):
        # NOTE: Avoid super() first because our primed defaults won't exist, and it'll think that's
        # a problem when it goes to do update().  Also avoid super() at the end because that will
        # just reset data to an empty dict and then update() will have the same problem.

        # Our attribute funnybusiness needs to be preempted by this UserData attribute existing
        # before anything attempts to read from it in the custom update() implementation.
        self.data = {}

        # Collect all class-level default attribute values for the initial ``data`` dict
        for cls in reversed(self.__class__.__mro__):
            init_dict = filter_safe_dict(cls.__dict__)
            self.data.update(init_dict)

        self.update(*args, _raise=_raise, **kwargs)

    def __getattr__(self, k):
        if k == 'data':
            return self.data
        return self.data[k]

    def __setattr__(self, k, v):
        super(InputMethod, self).__setattr__(k, v)
        if k == 'data':
            return
        self.data[k] = v

    def update(self, *args, _raise=True, **kwargs):
        data = flatten_dicts(*args, **kwargs)

        for k in filter_safe_dict(data, self.data.keys()):
            setattr(self, k, data.pop(k))

        # Raise an error for leftover attributes
        if len(data) and _raise:
            raise AttributeError("Invalid attributes for input method %r: %r -- valid attributes are %r" % (
                self.__class__,
                data,
                list(sorted(self.data.keys())),
            ))

    def serialize(self, instrument):
        """ Serializes a python representation of this input description. """

        info = self.data.copy()

        info['meta'] = {
            'method_class': self.__class__.__name__,
        }

        return info

    def clean(self, result):
        """ Clean the result and perform any necessary type coercion. """
        return result
