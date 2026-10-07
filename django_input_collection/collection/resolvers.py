import re
import logging
from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Manager, Model
from django.db.models.query import QuerySet

from . import exceptions


__all__ = [
    "resolve",
    "read_pass",
    "read_pass_cache",
    "memoize",
    "current_collector",
    "resolving_for",
    "current_answer_index",
    "Resolver",
    "InstrumentResolver",
    "AttributeResolver",
    "DebugResolver",
]

log = logging.getLogger(__name__)

registry = []

_read_pass_cache: ContextVar[dict | None] = ContextVar("resolver_read_pass", default=None)


_answer_index: ContextVar = ContextVar("resolver_answer_index", default=None)
_current_collector: ContextVar = ContextVar("resolver_collector", default=None)


@contextmanager
def read_pass(index=None):
    """Resolve each parent instrument once for the duration of a read-only evaluation pass.

    Wrap only code that evaluates conditions without writing inputs: answers are cached until
    the block exits, and the next pass re-reads them. Nested passes share the outer cache.
    ``index`` (an AnswerIndex) answers instrument: conditions from memory for its requests.
    """
    tokens = []
    if _read_pass_cache.get() is None:
        tokens.append((_read_pass_cache, _read_pass_cache.set({})))
    if index is not None:
        tokens.append((_answer_index, _answer_index.set(index)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def read_pass_cache():
    """The current pass's cache dict, or None outside a pass."""
    return _read_pass_cache.get()


def memoize(key, compute):
    """``compute()`` once per read pass for ``key`` (hashable); uncached outside a pass."""
    cache = _read_pass_cache.get()
    if cache is None:
        return compute()
    key = tuple(key) if isinstance(key, (list, tuple)) else (key,)  # a str stays one part
    full_key = ("memoize", *key)
    if full_key not in cache:
        cache[full_key] = compute()
    return cache[full_key]


def current_answer_index() -> "AnswerIndex | None":  # noqa: F821
    """The AnswerIndex the current read pass was given, or None."""
    return _answer_index.get()


def current_collector():
    """The collector testing conditions right now, or None."""
    return _current_collector.get()


@contextmanager
def resolving_for(collector):
    token = _current_collector.set(collector)
    try:
        yield
    finally:
        _current_collector.reset(token)


def _freeze(value):
    """Hashable form of resolver context; raises TypeError for values it can't key on."""
    if isinstance(value, Model):
        return (value._meta.label, value.pk)
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(v) for v in value)
    hash(value)
    return value


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
            # A missing gating instrument is routine; anything else is likely a broken hook.
            expected = isinstance(e, ObjectDoesNotExist)
            log.log(
                logging.DEBUG if expected else logging.WARNING,
                "Resolver %r raised an exception for instrument=%d, kwargs=%r, lookup=%r: %s",
                resolver.__class__,
                instrument.pk,
                kwargs,
                spec,
                error,
                exc_info=not expected,
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
        raise NotImplementedError


class InstrumentResolver(Resolver):
    """
    Expands an instrument reference to its CollectedInputs for the given ``context``, and its
    SuggestedResponses, should they be needed for any Case match types that require them.
    """

    name = "instrument"
    pattern = r"((?P<parent_pk>\d+)|(?P<measure>.+))"

    def search_requests(self, instrument, collector):
        """Own request first, then whatever the collector adds.

        Entries are CollectionRequests or their pks: the own request is always its pk, so the
        common case never loads the ``collection_request`` FK.
        """
        own_id = instrument.collection_request_id
        if collector is None or not collector.widens_condition_requests():
            return [own_id]
        requests = [own_id]
        for request in collector.get_condition_requests(instrument):
            if getattr(request, "pk", request) != own_id:
                requests.append(request)
        return requests

    def resolve(self, instrument, parent_pk=None, measure=None, **context):
        collector = current_collector()
        requests = self.search_requests(instrument, collector)
        index = current_answer_index()
        if index is not None:
            found = index.lookup(requests, parent_pk=parent_pk, measure=measure)
            if found is not None:
                values, suggested_values = found
                return {"data": list(values), "suggested_values": suggested_values}

        cache, key = _read_pass_cache.get(), None
        if cache is not None:
            try:
                request_ids = tuple(getattr(r, "pk", r) for r in requests)
                # Collectors that filter inputs differently must not share an entry.
                filter_key = collector.condition_cache_key() if collector is not None else None
                key = (request_ids, filter_key, parent_pk, measure, _freeze(context))
            except TypeError:
                key = None  # Unkeyable context: resolve uncached rather than risk a collision
        if key is not None and key in cache:
            values, suggested_values = cache[key]
            return {"data": list(values), "suggested_values": suggested_values}

        values, suggested_values = self._lookup(requests, parent_pk, measure, context, collector)
        if key is not None:
            cache[key] = (values, suggested_values)
        return {"data": list(values), "suggested_values": suggested_values}

    def _lookup(self, requests, parent_pk, measure, context, collector):
        from ..models import CollectionInstrument

        lookup = {"pk": parent_pk} if parent_pk else {"measure_id": measure}
        first = None
        for position, request in enumerate(requests):
            if parent_pk and position:
                break  # a pk names one instrument in the condition's own request
            parent = CollectionInstrument.objects.filter(
                collection_request=request, **lookup
            ).first()
            if parent is None:
                continue
            first = first or parent
            inputs = parent.collectedinput_set.filter_for_context(**context)
            if collector is not None:
                inputs = collector.filter_condition_inputs(inputs)
            values = list(inputs.values_list("data", flat=True))
            if values:
                # Lazy: match types that don't need suggestions never query them.
                return values, parent.suggested_responses.values_list("data", flat=True)
        if first is None:
            raise CollectionInstrument.DoesNotExist(
                f"No gating instrument {parent_pk or measure!r}"
            )
        return [], first.suggested_responses.values_list("data", flat=True)


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
            if isinstance(obj, (QuerySet, Manager)):
                if hasattr(obj, attr):
                    if callable(getattr(obj, attr)):
                        return getattr(obj, attr)()
                    return getattr(obj, attr)
            for branch_obj in obj:
                try:
                    branch_obj = self.resolve_dotted_path(branch_obj, attr)
                except Exception as error:
                    branch_obj = None
                    log.debug(
                        f"Resolver {self.__class__!r} trapped an inner exception while "
                        f"iterating attr={attr!r} ({self.__class__.__name__}) on object "
                        f"{branch_obj!r}; {error.__class__.__name__} - {error}"
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
