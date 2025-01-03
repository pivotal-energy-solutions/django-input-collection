import importlib
import hashlib
from inspect import isclass
import json

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Model, F

from ..encoders import CollectionSpecificationJSONEncoder
from ..models import AbstractBoundSuggestedResponse
from .matchers import matchers
from . import specifications, CollectionRequestQueryMinimizerMixin
from . import methods
from . import utils
from . import exceptions

__all__ = ["resolve", "Collector", "BaseAPICollector"]


registry = {}


def resolve(identifier):
    return registry[identifier]


def get_identifier(cls):
    path = ".".join((cls.__module__, cls.__name__))
    identifier = hashlib.sha256(path.encode()).hexdigest()
    return identifier


def register(cls):
    registry.setdefault(cls.get_identifier(), cls)


def fail_registration_action(cls, msg):
    raise exceptions.CollectorRegistrationException(msg % {"cls": cls})


class CollectorType(type):
    def __new__(cls, name, bases, attrs):
        cls = super(CollectorType, cls).__new__(cls, name, bases, attrs)

        if attrs.get("__noregister__", False):
            cls.get_identifier = cls.fail_get_identifier
            cls.register = cls.fail_register
        else:
            cls.__noregister__ = False  # Avoid inheritance confusion
            cls.get_identifier = classmethod(get_identifier)
            cls.register = classmethod(register)
            cls.register()
        return cls

    def fail_get_identifier(cls):
        fail_registration_action(
            cls,
            "Collector %(cls)r with __noregister__=True cannot be inspected for a registration identifier.",
        )

    def fail_register(cls):
        fail_registration_action(
            cls, "Collector %(cls)r with __noregister__=True cannot be registered."
        )


instrument_cache = {}  # collection_request_id: {measure_id: instrument}


class BaseCollector(object, metaclass=CollectorType):
    __version__ = (0, 0, 0, "dev")
    __noregister__ = True

    segment = None
    group = None
    groups = None
    specification_class = specifications.Specification

    types = None
    measure_types = None

    # TODO: Streamline how this will have to work for targetting response_policy settings, too.
    # I think it'll have to be something like a list of "match dicts" and the first one to match
    # all settings for the instrument will be used.
    type_methods = None
    measure_methods = None

    # Internals
    staged_data = None
    cleaned_data = None

    def __init__(self, collection_request, segment=None, group=None, groups=None, **context):
        self.collection_request = collection_request
        self.context = context

        def getfirst(first=None, *args):
            return first

        # Use 'segment' and 'groups' for the scope of the collection effort.
        # When 'segment' isn't given, translate a bare use of 'group' to 'segment'.
        self.groups = groups or []
        if segment and group:
            self.groups.append(group)
        self.segment = segment or self.segment or group

        # Specifying the 'groups' list 'group' is empty will, for a unofficial period of backward
        # compatibility, promote the first value to 'group', which was something like the behavior
        # before.
        self.group = group or (groups[0] if groups else None)

        self.types = self.get_types()
        self.measure_types = self.get_measure_types()
        self.type_methods = self.get_type_methods()
        self.measure_methods = self.get_measure_methods()

    # Main properties
    @property
    def specification(self):
        serializer = self.get_specification()
        return serializer.data

    @property
    def specification_json(self):
        return json.dumps(self.specification, cls=CollectionSpecificationJSONEncoder, indent=4)

    @property
    def serialized_data(self):
        # Save 255 queries
        instruments = (
            self.get_instruments()
            .prefetch_related("conditions__condition_group", "collectedinput_set")
            .select_related("response_policy")
        )
        serializer_class = self.get_serializer_class("instrument")
        serializer = serializer_class(
            instance=instruments,
            many=True,
            context={
                "collector": self,
                "collector_mixin": CollectionRequestQueryMinimizerMixin(collector=self),
            },
        )
        return serializer.data

    # Serialization utils
    def get_specification(self):
        return self.specification_class(self)

    def get_types(self):
        return self.types or {}

    def get_measure_types(self):
        return self.measure_types or {}

    def get_type_methods(self):
        """
        Returns a dictionary of type_ids to an ``InputMethod`` subclass.  Note that this is
        overridden by measure lookups specified in ``measure_methods``.
        """
        return self.type_methods or {}

    def get_measure_methods(self):
        """
        Returns a dictionary of measure_ids to an ``InputMethod`` subclass.  Note that this
        overrides measure lookups specified in ``type_methods``.
        """
        return self.measure_methods or {}

    def get_method_kwargs(self, instrument):
        """Returns constructor kwargs for the InputMethod subclass assigned to ``instrument``."""
        type_ref = self.get_type(instrument)
        return {
            "cleaner": type_ref.clean,
        }

    def get_method(self, instrument=None, measure=None):
        """
        Returns an InputMethod instance, determined by default by the instrument's measure_id in
        ``measure_methods``, or its type_id in ``type_methods``.
        """
        if instrument or measure:
            if instrument and measure:
                raise ValueError("Can't specify both 'instrument' and 'measure'")
            if measure:
                instrument = self.get_instrument(measure)

        if instrument is None:
            method = methods.InputMethod
        elif instrument.measure_id in self.measure_methods:
            method = self.measure_methods[instrument.measure_id]
        elif instrument.type_id in self.type_methods:
            method = self.type_methods[instrument.type_id]
        else:
            method = methods.InputMethod

        if isclass(method):
            method = method()
        method_kwargs = self.get_method_kwargs(instrument)
        method.update(**method_kwargs)

        return method

    def get_type_kwargs(self, instrument):
        """
        Returns constructor kwargs for the InstrumentType subclass assigned to ``instrument``.
        """
        return {}

    def get_type(self, instrument):
        """
        Returns a InstrumentType instance, determined by default by the instrument's type_id in
        ``types``.
        """

        if instrument is None:
            type_ref = methods.InputMethod
        elif instrument.type_id in self.measure_types:
            type_ref = self.measure_types[instrument.type_id]
        elif instrument.type_id in self.types:
            type_ref = self.types[instrument.type_id]
        else:
            type_ref = methods.InputMethod

        type_kwargs = self.get_type_kwargs(instrument)
        type_ref = type_ref(**type_kwargs)

        return type_ref

    def get_instruments(self, active=None, required=None):
        """
        Returns the queryset of instruments matching any flags that are set.  ``None`` values for
        ``active`` and ``required`` mean that instruments can be returned with mixed True and False
        values for that particular flag.

        ``active`` can alternatively be the shortname of an in-use condition resolver type, such as
        'instrument' or 'attribute'.  Only instruments with conditions referencing that resolver
        will be returned.

        ``active`` can alternatively be a list of shortnames.

        Any specified active value (direct or in a list) can be a dict mapping that one name to a
        desired active status, True or False.  Specifying ``None`` is the equivalent of providing
        the resolver name directly.

        A ``None`` in a list will target instruments without any conditions at all.
        A ``True`` or ``False`` in a list will include any passing/failing instrument, respectively.
        """
        queryset = self.collection_request.collectioninstrument_set.all()

        if required is not None:
            queryset = queryset.filter(response_policy__required=required)

        if active is not None:
            if not isinstance(active, (list, tuple)):
                active = [active]

            include_pks = set()

            # Interpret each active flag and add the resulting pks to the inclusion list.
            for flag in active:
                flagged_pks = set()
                resolver_name = None
                predicate = lambda i, f: self.is_instrument_allowed(i) == f  # noqa: E731
                if flag is None:
                    # Get instruments without conditions
                    pk_list = queryset.filter(conditions=None).values_list("pk", flat=True)
                    include_pks.add(set(pk_list))
                else:
                    flag_queryset = queryset

                    # Unpack syntaxes
                    if isinstance(flag, str):
                        # Direct string reference
                        resolver_name = flag
                        flag = True
                    elif isinstance(flag, dict):
                        # Single-item dict, string reference mapping to a desired active flag
                        resolver_name, flag = list(flag.items())[0]

                    if callable(flag):
                        predicate = flag
                        flag = False

                    if resolver_name:
                        flag_queryset = queryset.filter_for_condition_resolver(resolver_name)

                    # Check each instrument for the desired pass/fail result
                    for instrument in flag_queryset:
                        if flag is None or predicate(instrument, flag):
                            flagged_pks.add(instrument.pk)

                include_pks |= flagged_pks

            queryset = queryset.filter(pk__in=include_pks)

        return queryset

    def get_instrument(self, measure):
        """Returns the instrument corresponding to ``measure``, or None if one doesn't exist."""
        if isinstance(measure, Model):
            measure = measure.pk

        cache = instrument_cache.setdefault(self.collection_request.id, {})
        if measure not in cache:
            instrument = self.get_instruments().filter(measure_id=measure).first()
            cache[measure] = instrument
        return cache[measure]

    def get_suggested_responses(self, instrument=None, measure=None):
        if instrument or measure:
            if instrument and measure:
                raise ValueError("Can't specify both 'instrument' and 'measure'")
            if measure:
                instrument = self.get_instrument(measure)
        else:
            raise ValueError("Must specify one of 'instrument' and 'measure'")

        # Return swappable model references with the associated input
        return instrument.bound_suggested_responses.annotate(data=F("suggested_response__data"))

    def get_inputs(self, instrument=None, measure=None):
        """
        Returns the queryset of inputs for this collection request.  If ``instrument`` or
        ``measure`` are given,
        """

        if instrument or measure:
            if instrument and measure:
                raise ValueError("Can't specify both 'instrument' and 'measure'")

        # Tidy as lists
        instruments = instrument
        if instrument and not isinstance(instruments, (list, tuple)):
            instruments = [instrument]
        measures = measure
        if measure and not isinstance(measures, (list, tuple)):
            measures = [measure]

        # Convert to instrument references
        if measure:
            instruments = [self.get_instrument(m) for m in measures]

        queryset = self.collection_request.collectedinput_set.filter_for_context(**self.context)

        # Enforce filtering when filtering was requested.  An empty instruments list might not mean
        # that no filter was requested at all.
        if not instruments and not (instrument or measure):
            return queryset

        return queryset.filter(instrument__in=instruments)

    def get_data_display(self, instrument=None, measure=None):
        """Formats the CollectedInput queryset for the given instrument as a string."""
        method = self.get_method(instrument=instrument, measure=measure)

        queryset = self.get_inputs(instrument=instrument, measure=measure)
        values = list(map(self.extract_data_input, queryset.values_list("data", flat=True)))

        for i, value in enumerate(values):
            values[i] = method.get_data_display(value)

        return ", ".join(map(str, values))

    # Instrument/Input runtime hooks
    def get_conditional_check_value(self, data):
        """Coerces match data from a SuggestedResponse or Case for comparison with an input."""
        return data

    def get_active_conditional_instruments(self, instrument):
        """
        Tests the conditions on the instrument's sub-instruments and returns those that pass.
        """
        allowed = []
        for child in instrument.get_child_instruments():
            if self.is_instrument_allowed(child):
                allowed.append(child)
        return allowed

    def is_condition_successful(self, condition, **kwargs):
        """
        Like ``is_instrument_allowed()``, except that it tests only the given condition.  Using this
        method instead of ``condition.test()`` directly has the benefit of allowing the collector
        to implicitly send ``key_input``, ``key_case``, and ``resolver_fallback_data``.
        """
        if "resolver_fallback_data" not in kwargs:
            kwargs["resolver_fallback_data"] = self.make_payload_data(condition.instrument, None)
        key_input = self.extract_data_input
        key_case = self.get_conditional_check_value
        return condition.test(key_input=key_input, key_case=key_case, **kwargs)

    def is_instrument_allowed(self, instrument, **kwargs):
        """
        Returns True when the given instrument passes all related conditions limiting its use.  The
        ``resolver_fallback_data`` kwarg is forwarded to ``Condition.test()``, where a failed attempt at
        resolving its ``data_getter`` will result in the use of the given default instead.
        """
        if "resolver_fallback_data" not in kwargs:
            kwargs["resolver_fallback_data"] = self.make_payload_data(instrument, None)
        key_input = self.extract_data_input
        key_case = self.get_conditional_check_value
        return instrument.test_conditions(
            key_input=key_input, key_case=key_case, context=self.context, **kwargs
        )

    def is_measure_allowed(self, measure, **kwargs):
        instrument = self.get_instrument(measure)
        return self.is_instrument_allowed(instrument, **kwargs)

    def is_input_allowed(self, instrument, user=None):
        """
        Returns True when the given instrument passes checks against flags on its CollectionRequest.
        If ``user`` is given, it will be used instead of self.context['user'] for checking the
        per-user max on the related response_policy.
        """
        manager = instrument.collectedinput_set

        request_flags = instrument.collection_request.get_flags()

        if user is None:
            user = self.context.get("user")
        if user and not isinstance(user, AnonymousUser):
            user_max = request_flags["max_instrument_inputs_per_user"]
            if user_max is not None:
                existing_inputs = manager.filter_for_context(**self.context)
                input_count = existing_inputs.count()
                if input_count >= user_max:
                    return False

        total_max = request_flags["max_instrument_inputs"]
        if total_max is not None:
            no_user_context = self.context.copy()
            no_user_context.pop("user", None)
            existing_inputs = manager.filter_for_context(**no_user_context)
            input_count = existing_inputs.count()
            if input_count >= total_max:
                return False

        return True

    def get_cleaners(self, instrument=None, measure=None, suggested_response=None):
        cleaners = []

        method = self.get_method(instrument=instrument, measure=measure)
        cleaners.append(method.clean)

        if suggested_response:
            cleaners.append(suggested_response.clean)

        return cleaners

    def clean(self, *payloads, **kwargs):
        """
        Sends all given payloads to ``clean_payload()`` and stores then returns their
        ``cleaned_data`` as a list to match.  If a single payload is given, a direct reference will
        be stored instead of a single-item list holding it.

        If no payloads are given, the data currently remembered by ``stage()`` will be used instead,
        be it a list or direct payload reference.
        """

        if not hasattr(self, "_clean_index") or not isinstance(self.staged_data, list):
            self._clean_index = 0  # Set to default

        if not payloads:
            payloads = self.staged_data
            if payloads is None:
                raise ValueError(
                    "Must provide 'payload' argument or use collector.stage(payload_list)."
                )

        # Do an early resolve of these kwargs that are destined for clean_payload(), so that this
        # doesn't have to be done once for each payload.
        instrument = kwargs.get("instrument")
        measure = kwargs.pop("measure", None)
        if instrument or measure:
            if instrument and measure:
                raise ValueError("Can't specify both 'instrument' and 'measure'")
            if measure:
                kwargs["instrument"] = self.get_instrument(measure=measure)

        payload_list = payloads
        single = isinstance(payloads, dict)  # staged_data could be a single direct ref
        if single:
            payload_list = [payloads]

        for payload in payload_list[self._clean_index :]:
            payload = self.clean_payload(payload)

            if single:
                self.cleaned_data = payload  # Loop will end asap and return this reference
            else:
                if self.cleaned_data is None:
                    self.cleaned_data = []
                self.cleaned_data.append(payload)

        # Note that this should be 1 after a single unwrapped payload dict is cleaned.  That item
        # went to self.cleaned_data as a direct reference, but subsequent calls to clean() may want
        # to wrap a list around what's already there so it can append to that.
        self._clean_index = len(payload_list)

        return self.cleaned_data

    def clean_payload(self, payload, instrument=None, measure=None, **skip_options):
        """
        Cleans a payload dict of kwargs for the current CollectedInput model.  If the payload is not
        given, the data last remembered by ``collector.stage(data_list)`` will be used.  Note that
        when the payload is an iterable, providing ``instrument`` or ``message`` will overwrite the
        instrument reference for all items in the list.  To use different instruments, set the
        same key in the payload data where it can be locally discovered.
        """

        if not instrument:
            # Look for values in the payload instead.
            # Note that both can be specified in this scenario since the payload can be
            # arbitrary, but 'instrument' has priority, then 'measure'.
            instrument = payload.get("instrument")
            if instrument is None:
                if "measure" in payload:
                    measure = payload["measure"]
                    if measure:
                        instrument = self.get_instrument(measure)
                    if instrument is None:
                        raise ValueError(
                            "Invalid measure %r, no instrument can be resolved for: %r"
                            % (measure, payload)
                        )
                else:
                    raise ValueError(
                        "Data does not have 'instrument' or 'measure': %r" % (payload,)
                    )

        if not skip_options.get("skip_availability"):
            is_unavailable = not self.is_instrument_allowed(instrument)
            if is_unavailable:
                raise ValidationError(
                    "Availability conditions failed for instrument %r" % instrument.pk
                )

        if not skip_options.get("skip_capacity"):
            at_capacity = not self.is_input_allowed(instrument)
            if at_capacity:
                raise ValidationError("No new inputs allowed for instrument %r" % instrument.pk)

        payload["instrument"] = instrument
        payload["data"] = self.clean_data(instrument, payload["data"])
        return payload

    def clean_data(self, instrument, data):
        """Cleans the block of input data for storage."""

        # Ensure ResponsePolicy flags are respected
        policy_flags = instrument.response_policy.get_flags()
        allows_multiple = policy_flags["multiple"]
        if allows_multiple and not isinstance(data, list):
            data = [data]
        if not allows_multiple and isinstance(data, list):
            raise ValidationError("Multiple inputs are not allowed")

        # Process each bit in the input, forcing a list in case there is only one
        is_plural = isinstance(data, list)
        if not is_plural:
            data = [data]

        for i, item in enumerate(data):
            data[i] = self.clean_input(instrument, item)

        if not is_plural:
            data = data[0]

        return data

    def clean_input(self, instrument, data):
        """
        Cleans a single input data point for storage, either directly or within a list of plural
        inputs (if ``response_policy.multiple`` allows it).
        """

        # Ensure ResponsePolicy flags are respected
        policy_flags = instrument.response_policy.get_flags()
        disallow_custom = policy_flags["restrict"]

        # Ensure {'_suggested_response': pk} is swapped out for real underlying data
        bound_responses = self.get_suggested_responses(instrument)
        bound_lookups = bound_responses.in_bulk()
        data = utils.expand_suggested_responses(instrument, bound_lookups, data)

        # Keep a possible SuggestedResponse result for invoking its ``clean()``
        suggested_response = None
        if isinstance(data, AbstractBoundSuggestedResponse):
            suggested_response = data
            data = suggested_response.data

        cleaners = self.get_cleaners(instrument, suggested_response=suggested_response)
        for cleaner in cleaners:
            data = cleaner(data)

        # Enforce the disallow_custom flag from clean_data()
        allowed_values = None
        if disallow_custom:
            allowed_values = set(bound_responses.values_list("suggested_response__data", flat=True))
            if allowed_values and not matchers.all_suggested(data, allowed_values):
                raise ValidationError(
                    "[CollectionInstrument id=%r] Input %r is not from the list of suggested responses"
                    % (instrument.id, data)
                )

        return data

    def raise_error(self, exception):
        raise exception

    def make_payload(self, instrument, data, **kwargs):
        """Returns a dict of model field values for storage."""
        payload = dict(
            kwargs,
            **{
                "instrument": instrument,
                "data": self.make_payload_data(instrument, data, **kwargs),
                # Disallow data integrity funnybusiness
                "collection_request": instrument.collection_request,
                "user": self.context.get("user"),
                "collector_class": ".".join(
                    filter(
                        bool,
                        (
                            self.__class__.__module__,
                            self.__class__.__name__,
                        ),
                    )
                ),
                "collector_id": self.get_identifier(),
                "collector_version": ".".join(map(str, self.__version__)),
                "version": ".".join(map(str, BaseCollector.__version__)),
            },
        )
        return payload

    def make_payload_data(self, instrument, data, **kwargs):
        """
        Coerces ``data`` for storage on the active input model (CollectedInput or swapped).  Note
        that ``data`` may be sent as None to represent an empty version of the payload 'data' value.
        """
        return data

    def extract_data_input(self, data):
        """Extracts the data contained in a well-formed payload['data'] value."""
        return data

    # Granular storage api
    def store(self, instrument, data, instance=None, **model_field_values):
        """
        Creates a new CollectedInput instance for the given data.  Any additional kwargs are sent to
        the manager's ``create()`` method, in case the CollectedInput model has been swapped and
        requires additional fields to successfully save.
        """

        from .. import models

        CollectedInput = models.get_input_model()

        payload = self.make_payload(instrument, data, **model_field_values)

        pk = None
        if instance is not None:
            pk = instance.pk
        instance, created = CollectedInput.objects.update_or_create(pk=pk, defaults=payload)

        return instance

    def remove(self, instrument, instance):
        """Removes a given CollectedInput from the instrument."""
        instance.delete()

    # Bulk data handling
    def clear(self):
        self.staged_data = None
        self.cleaned_data = None

    def stage(self, payloads, clean=True, extend=None, **kwargs):
        """
        Remembers given ``data`` (dict or list of dicts) for a future call to ``clean()`` and
        ``save()``.  Any new
        """
        if not payloads:
            raise ValueError("At least one payload dict must be provided.")

        self.cleaned_data = None

        if isinstance(payloads, dict):
            payloads = [payloads]
        else:
            payloads = list(payloads)

        for payload in payloads:
            payload.update(kwargs)

        single_staged = self.staged_data is not None and isinstance(self.staged_data, dict)
        single_given = len(payloads) == 1
        if extend is None and single_given and single_staged:
            extend = True
            self.staged_data = [self.staged_data]  # Prep for extend()

        if extend:
            self.staged_data.extend(payloads)
        elif single_given:
            self.staged_data = payloads[0]
        else:
            self.staged_data = payloads  # List with extend False (or None)

        if not extend:
            self._clean_index = 0

        # Clean all at once so self.cleaned_data is not just the last individual clean result
        if clean:
            self.clean()

    def save(self, **kwargs):
        """Calls store() for current staged data or data list."""
        if self.staged_data is None:
            raise ValueError("First use collector.stage([data_iterable]).")
        if self.cleaned_data is None:
            raise ValueError("Data is not cleaned.")

        save_list = self.cleaned_data
        single = isinstance(save_list, dict)
        if single:
            save_list = [single]

        items = []
        for payload in save_list:
            item_kwargs = dict(payload, **kwargs)
            items.append(self.store(**item_kwargs))

        if single:
            return items[0]
        return items


class Collector(BaseCollector):
    segment = "default"


class BaseAPICollector(Collector):
    __noregister__ = True  # Perpetuate the registration opt-out for this alternate base
    specification_class = specifications.BaseAPISpecification
