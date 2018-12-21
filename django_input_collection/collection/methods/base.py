from functools import reduce
import inspect

from django.core.exceptions import ValidationError
from django.utils.text import format_lazy

from ...compat import UserDict

__all__ = ['InputMethod']


def flatten_dicts(*args, **kwargs):
    return reduce(lambda d, d2: dict(d, **d2), args + (kwargs,), {})


def filter_safe_dict(data, attrs=None, exclude=None):
    """
    Returns current names and values for valid writeable attributes. If ``attrs`` is given, the
    returned dict will contain only items named in that iterable.
    """

    def is_member(cls, k):
        v = getattr(cls, k)
        checks = [
            not k.startswith('_'),
            not inspect.ismethod(v) or getattr(v, 'im_self', True),
            not inspect.isfunction(v),
            not isinstance(v, (classmethod, staticmethod, property))
        ]
        return all(checks)

    cls = None
    if inspect.isclass(data):
        cls = data
        data = {k: getattr(cls, k) for k in dir(cls) if is_member(cls, k)}

    ret = {}
    for k, v in data.items():
        checks = [
            not k.startswith('_'),
            not inspect.ismethod(v) or getattr(v, 'im_self', True),
            not isinstance(v, (classmethod, staticmethod, property)),
            not attrs or (k in attrs),
            not exclude or (k not in exclude),
        ]

        if all(checks):
            ret[k] = v
    return ret


base_errors = {
    Exception: '{exception}',
}

class InputMethod(object):
    """
    A stateless encapsulation of the components required to obtain and coerce data for an arbitrary
    CollectionInstrument.  Its job is to produce something that supports interaction through
    whatever external methodology is required to obtain data, and then to receive such data once
    that external methodology has complete.
    """

    data_type = None

    # Internals determined at runtime via initialization kwargs
    cleaner = None
    errors = None

    def __init__(self, *args, **kwargs):
        # Collect all class-level default attribute values for the initial ``data`` dict
        for cls in reversed(self.__class__.__mro__):
            init_dict = filter_safe_dict(cls)
            self.update(init_dict)

        # Do usual init
        self.update(*args, **kwargs)

        # Flatten defined errors
        if self.errors is None:
            self.errors = {}
        self.errors = dict(base_errors, **self.errors)

    def update(self, *args, **kwargs):
        _raise = kwargs.pop('_raise', True)

        data = flatten_dicts(*args, **kwargs)

        safe_data = filter_safe_dict(data)
        valid_keys = list(safe_data.keys())

        for k in valid_keys:
            setattr(self, k, data.pop(k))

        # Raise an error for leftover attributes
        if len(data) and _raise:
            raise AttributeError("Disallowed keys/values for %r: %r" % (
                self.__class__.__name__, data,
            ))

    def get_constraints(self):
        return {}

    def get_data_display(self, value):
        return unicode(value)

    @property
    def data(self):
        exclude = ('cleaner', 'errors')
        if self.data_type is None:
            exclude += ('data_type',)
        return filter_safe_dict(self.__dict__, exclude=exclude)

    # Serialization
    def serialize(self, **kwargs):
        """ Serializes a simple representation of this input method. """
        data = self.data.copy()
        data['meta'] = {
            'method_class': '.'.join([self.__module__, self.__class__.__name__]),
            'data_type': self.data_type,
        }
        data['constraints'] = self.get_constraints()
        return data

    # Cleaning
    def clean_input(self, data):
        """ Runs ``clean()`` and traps any exception as a ValidationError. """
        try:
            data = self.clean(data)
        except Exception as exception:
            error = self.get_error(exception, data=data, exception=exception)
            raise ValidationError(error)
        return data

    def clean(self, data):
        """ Runs ``cleaner`` callable with ``data``. """
        if self.cleaner:
            return self.cleaner(data)
        return data

    # Errors
    def get_error(self, code, **format_kwargs):
        """ Returns a formatted message string for the given ``code``. """
        if isinstance(code, Exception):
            code = self.get_best_exception_code(code)

        message = self.errors[code]
        return format_lazy(message, **format_kwargs)

    def get_best_exception_code(self, exception):
        """ Translate given exception to best isinstance() match in the ``errors`` keys. """
        exception_rules = list(
            code for code, message in self.errors.items() if isinstance(code, Exception)
        )

        for lookup_types in exception_rules:
            is_exception = isinstance(lookup_types, Exception)
            use_isinstance = isinstance(lookup_types, tuple) and not isinstance(lookup_types[0], Exception)
            if not is_exception and not use_isinstance:
                continue

            is_applicable = isinstance(exception, lookup_types)
            is_more_specific = (best_code is None or isinstance(exception, best_code))
            if is_applicable and is_more_specific:
                best_code = lookup_types

        return best_code
