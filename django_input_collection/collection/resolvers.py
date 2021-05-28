import re
import logging

from django.db.models import Manager
from django.db.models.query import QuerySet

from . import exceptions


__all__ = ["resolve", "Resolver", "InstrumentResolver", "AttributeResolver", "DebugResolver"]

log = logging.getLogger(__name__)

registry = []


def resolve(instrument, spec, fallback=None, raise_exception=True, **context):
    """
    Uses the first registered resolver where ``spec`` matches its pattern, and returns a 3-tuple of
    the resolver used, the dict of kwargs for ``collection.matchers.test_condition_case()``, and
    any exception raised during attribute traversal.
    """

    for resolver in registry:
        result = resolver.apply(spec)
        if result is False:
            continue

        error = None
        kwargs = dict(context, **result)
        try:
            data_info = resolver.resolve(instrument=instrument, **kwargs)
        except Exception as e:
            error = e
            data_info = {
                "data": fallback,
            }
            log.debug(
                "Resolver %r raised an exception for instrument=%d, kwargs=%r, lookup=%r: %s",
                resolver.__class__,
                instrument.pk,
                kwargs,
                spec,
                error,
            )

        return (resolver, data_info, error)

    if raise_exception:
        raise ValueError(
            "Data getter %r does not match known resolvers in '%s.registry': %r"
            % (
                spec,
                __name__,
                {resolver.full_pattern: resolver.__class__ for resolver in registry},
            )
        )
    return (None, {}, None)


def register(cls):
    registry.append(cls())


def fail_registration_action(cls, msg):
    raise exceptions.CollectorRegistrationException(msg % {"cls": cls})


class ResolverType(type):
    def __new__(cls, name, bases, attrs):
        cls = super(ResolverType, cls).__new__(cls, name, bases, attrs)

        if attrs.get("__noregister__", False):
            cls.register = cls.fail_register
        else:
            cls.__noregister__ = False  # Avoid inheritance confusion
            cls.register = classmethod(register)
            cls.register()
        return cls

    def fail_register(cls):
        fail_registration_action(
            cls, "Resolver %(cls)r with __noregister__=True cannot be registered."
        )


class Resolver(metaclass=ResolverType):
    """
    Matches a ``Condition.data_getter`` string with a pattern, and extracts a dict of kwargs
    suitable for sending to ``collection.matchers.test_condition_case()``.
    """

    __noregister__ = True

    name = None
    pattern = None

    @property
    def full_pattern(self):
        return r"^{}:{}$".format(self.name, self.pattern)

    def apply(self, spec):
        """Returns pattern match groups if the spec applies to this pattern, or False."""
        match = re.match(self.full_pattern, spec)
        if match:
            return match.groupdict()
        return False

    def resolve(self, **context):
        """Returns a dict of data found during this resolver's execution."""
        raise NotImplemented


class InstrumentResolver(Resolver):
    """
    Expands an instrument reference to its CollectedInputs for the given ``context``, and its
    SuggestedResponses, should they be needed for any Case match types that require them.
    """

    name = "instrument"
    pattern = r"((?P<parent_pk>\d+)|(?P<measure>.+))"

    def resolve(self, instrument, parent_pk=None, measure=None, **context):
        from ..models import CollectionInstrument

        if parent_pk:
            lookup = {"pk": parent_pk}
        elif measure:
            lookup = {"measure_id": measure}
        instrument = CollectionInstrument.objects.get(
            collection_request=instrument.collection_request, **lookup
        )
        inputs = instrument.collectedinput_set.filter_for_context(**context)
        values = list(inputs.values_list("data", flat=True))

        # Avoid list coercion at this step so that match types not requiring this query won't end
        # up hitting the database.
        suggested_values = instrument.suggested_responses.values_list("data", flat=True)

        return {
            "data": values,
            "suggested_values": suggested_values,
        }


class AttributeResolver(Resolver):
    """
    Accepts a dotted attribute path that will be traversed to produce data, starting from the
    conditional instrument this condition is checking.  Dictionaries will use index lookup instead
    of attributes.  Attributes that resolve to callables will be called with no arguments.
    Attributes that resolve to simple iterables (including querysets and model managers) will each
    trigger the remaining lookups, with the results compiled as a list.
    """

    name = "attr"
    pattern = r"(?P<dotted_path>.*)"

    def resolve(self, instrument, dotted_path, **context):
        result = self.resolve_dotted_path(instrument, dotted_path)
        return {
            "data": result,
        }

    def resolve_dotted_path(self, obj, attr):
        remainder = None

        if isinstance(obj, dict):
            obj = obj[attr]
        elif isinstance(obj, (Manager, QuerySet, list, tuple, set)):
            branch_objs = []
            for branch_obj in obj:
                try:
                    branch_obj = self.resolve_dotted_path(branch_obj, attr)
                except Exception as error:
                    branch_obj = None
                    log.debug(
                        "Resolver %r trapped an inner exception while iterating attr=%r (%s) object %r: %s",
                        self.__class__,
                        attr,
                        obj.__class__.__name__,
                        branch_obj,
                        error,
                    )
                branch_objs.append(branch_obj)
            obj = branch_objs
        else:
            if "." in attr:
                attr, remainder = attr.split(".", 1)
            obj = getattr(obj, attr)

            # Convert types we don't want to handle directly
            if isinstance(obj, Manager):
                obj = obj.all()
            elif callable(obj):
                obj = obj()

        if remainder:
            return self.resolve_dotted_path(obj, remainder)

        return obj


class DebugResolver(Resolver):
    """
    Accepts a literal python value to be evaluated in-place.  The result should be a dict with at
    least a ``data`` key, and possibly a ``suggested_values`` key set to a list.
    """

    name = "debug"
    pattern = r"(?P<expression>.*)"

    def resolve(self, instrument, expression, **context):
        result = eval(expression, {}, {})
        return result
