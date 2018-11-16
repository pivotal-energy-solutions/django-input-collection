import re
import logging

import six

from . import exceptions


__all__ = ['Resolver', 'resolve']

log = logging.getLogger(__name__)

registry = []


class unset(object):
    pass


def resolve(instrument, spec, fallback=unset, raise_exception=True, **context):
    """
    Uses the first registered resolver where ``spec`` matches its pattern, and returns a 3-tuple of
    the resolver used, the dict of kwargs for ``collection.matchers.test_condition_case()``, and
    any exception raised during attribute traversal.
    """

    if fallback is unset:
        fallback = {'data': None}

    for resolver in registry:
        result = resolver.apply(spec)
        if result is not False:
            error = None
            kwargs = dict(context, **result)
            try:
                data = resolver.resolve(instrument=instrument, **kwargs)
            except Exception as error:
                data = fallback
                log.info("Resolver %r raised an exception for instrument=%d, kwargs=%r, lookup=%r: %s",
                         resolver.__class__, instrument.pk, kwargs, spec, error)
            return (resolver, data, error)

    if raise_exception:
        raise ValueError("Data getter %r does not match known resolvers in '%s.registry': %r" % (
            spec, __name__, {resolver.pattern: resolver.__class__ for resolver in registry},
        ))
    return (None, {}, None)


def register(cls):
    registry.append(cls())


def fail_registration_action(cls, msg):
    raise exceptions.CollectorRegistrationException(msg % {'cls': cls})


class ResolverType(type):
    def __new__(cls, name, bases, attrs):
        cls = super(ResolverType, cls).__new__(cls, name, bases, attrs)

        if attrs.get('__noregister__', False):
            cls.register = cls.fail_register
        else:
            cls.__noregister__ = False  # Avoid inheritance confusion
            cls.register = classmethod(register)
            cls.register()
        return cls

    def fail_register(cls):
        fail_registration_action(cls, "Resolver %(cls)r with __noregister__=True cannot be registered.")


@six.add_metaclass(ResolverType)
class Resolver(object):
    """
    Matches a ``Condition.data_getter`` string with a pattern, and extracts a dict of kwargs
    suitable for sending to ``collection.matchers.test_condition_case()``.
    """
    __noregister__ = True

    pattern = None

    def apply(self, spec):
        """ Returns pattern match groups if the spec applies to this pattern, or False. """
        match = re.match(self.pattern, spec)
        if match:
            return match.groupdict()
        return False

    def resolve(self, **context):
        """ Returns a dict of data found during this resolver's execution. """
        raise NotImplemented


class InstrumentResolver(Resolver):
    """
    Expands an instrument reference to its CollectedInputs for the given ``context``, and its
    SuggestedResponses, should they be needed for any Case match types that require them.
    """

    pattern = r'^instrument:((?P<parent_pk>\d+)|(?P<measure>.+))$'

    def resolve(self, instrument, parent_pk=None, measure=None, **context):
        from ..models import CollectionInstrument
        if parent_pk:
            lookup = {'pk': measure}
        elif measure:
            lookup = {'measure_id': measure}
        instrument = CollectionInstrument.objects.get(**lookup)
        inputs = instrument.collectedinput_set.filter_for_context(**context)
        values = list(inputs.values_list('data', flat=True))

        # Avoid list coercion at this step so that match types not requiring this query won't end
        # up hitting the database.
        suggested_values = instrument.suggested_responses.values_list('data', flat=True)

        return {
            'data': values,
            'suggested_values': suggested_values,
        }


class DebugResolver(Resolver):
    """
    Accepts a literal python value to be evaluated in-place.  The result should be a dict with at
    least a ``data`` key, and possibly a ``suggested_values`` key set to a list.
    """

    pattern = r'^debug:(?P<expression>.*)$'

    def resolve(self, instrument, expression, **context):
        result = eval(expression, {}, {})
        return result