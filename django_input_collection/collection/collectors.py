import importlib
import hashlib
from inspect import isclass
import json

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Model

import six

from ..encoders import CollectionSpecificationJSONEncoder
from .matchers import matchers
from . import specifications
from . import methods
from . import utils
from . import exceptions

__all__ = ['resolve', 'Collector', 'BaseAPICollector']


registry = {}


def resolve(identifier):
    return registry[identifier]


def get_identifier(cls):
    path = '.'.join((cls.__module__, cls.__name__))
    identifier = hashlib.sha256(path.encode()).hexdigest()
    return identifier


def register(cls):
    registry.setdefault(cls.get_identifier(), cls)


def fail_registration_action(cls, msg):
    raise exceptions.CollectorRegistrationException(msg % {'cls': cls})


class CollectorType(type):
    def __new__(cls, name, bases, attrs):
        cls = super(CollectorType, cls).__new__(cls, name, bases, attrs)

        if attrs.get('__noregister__', False):
            cls.get_identifier = cls.fail_get_identifier
            cls.register = cls.fail_register
        else:
            cls.__noregister__ = False  # Avoid inheritance confusion
            cls.get_identifier = classmethod(get_identifier)
            cls.register = classmethod(register)
            cls.register()
        return cls

    def fail_get_identifier(cls):
        fail_registration_action(cls, "Collector %(cls)r with __noregister__=True cannot be inspected for a registration identifier.")

    def fail_register(cls):
        fail_registration_action(cls, "Collector %(cls)r with __noregister__=True cannot be registered.")


@six.add_metaclass(CollectorType)
class BaseCollector(object):
    __version__ = (0, 0, 0, 'dev')
    __noregister__ = True

    group = 'default'
    condition_resolver_fallback = {'data': None}
    specification_class = specifications.Specification

    # TODO: Streamline how this will have to work for targetting response_policy settings, too.
    # I think it'll have to be something like a list of "match dicts" and the first one to match
    # all settings for the instrument will be used.
    type_methods = None
    measure_methods = None

    def __init__(self, collection_request, group=None, **context):
        self.collection_request = collection_request
        self.context = context
        if group:
            self.group = group

        self.type_methods = self.get_type_methods()
        self.measure_methods = self.get_measure_methods()

    # Main properties
    @property
    def specification(self):
        serializer = self.get_specification()
        return serializer.data

    @property
    def specification_json(self):
        return json.dumps(self.specification, cls=CollectionSpecificationJSONEncoder)

    # Serialization utils
    def get_specification(self):
        return self.specification_class(self)

    def get_type_methods(self):
        return self.type_methods or {}

    def get_measure_methods(self):
        return self.measure_methods or {}

    def get_method_kwargs(self, instrument):
        return {}

    def get_method(self, instrument):
        method = methods.InputMethod

        if instrument.measure_id in self.measure_methods:
            method = self.measure_methods[instrument.measure_id]
        elif instrument.type_id in self.type_methods:
            method = self.type_methods[instrument.type_id]

        if isclass(method):
            method = method()

        method_kwargs = self.get_method_kwargs(instrument)
        method.update(**method_kwargs)

        return method

    def get_instruments(self):
        return self.collection_request.collectioninstrument_set.all()

    def get_active_instruments(self):
        """ Returns an ordered list of currenty activated instruments. """
        instruments = []
        for instrument in self.get_instruments():
            if self.is_instrument_allowed(instrument):
                instruments.append(instrument)
        return instruments

    def get_instrument(self, measure):
        """ Returns the instrument corresponding to ``measure``, or None if one doesn't exist. """
        if isinstance(measure, Model):
            measure = measure.pk

        return self.get_instruments().filter(measure_id=measure).first()

    def get_inputs(self, instrument=None, measure=None):
        """
        Returns the queryset of inputs for this collection request.  If ``instrument`` or
        ``measure`` are given, 
        """
        queryset = self.collection_request.collectedinput_set.filter_for_context(**self.context)
        if instrument or measure:
            if instrument and measure:
                raise ValueError("Can't specify both 'instrument' and 'measure'")
            if measure:
                instrument = self.get_instrument(measure)
            queryset = queryset.filter(instrument=instrument)
        return queryset

    # Instrument/Input runtime hooks
    def get_conditional_input_value(self, data):
        """ Coerces a CollectedInput's stored data for comparison with Case match data. """
        return data

    def get_conditional_check_value(self, data):
        """ Coerces match data from a SuggestedResponse or Case for comparison with an input. """
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
        to implicitly send ``key_input``, ``key_case``, and ``condition_resolver_fallback``.
        """
        if 'resolver_fallback' not in kwargs:
            kwargs['resolver_fallback'] = self.condition_resolver_fallback
        key_input = self.get_conditional_input_value
        key_case = self.get_conditional_check_value
        return condition.test(key_input=key_input, key_case=key_case, **kwargs)

    def is_instrument_allowed(self, instrument, **kwargs):
        """
        Returns True when the given instrument passes all related conditions limiting its use.  The
        ``resolver_fallback`` kwarg is forwarded to ``Condition.test()``, where a failed attempt at
        resolving its ``data_getter`` will result in the use of the given default instead.
        """
        if 'resolver_fallback' not in kwargs:
            kwargs['resolver_fallback'] = self.condition_resolver_fallback
        key_input = self.get_conditional_input_value
        key_case = self.get_conditional_check_value
        return instrument.test_conditions(key_input=key_input, key_case=key_case,
                                          context=self.context, **kwargs)

    def is_measure_allowed(self, measure, **kwargs):
        instrument = self.get_instrument(measure)
        return self.is_instrument_allowed(instrument, **kwargs)

    def is_input_allowed(self, instrument):
        """
        Returns True when the given instrument passes checks against flags on its CollectionRequest.
        """
        manager = instrument.collectedinput_set

        request_flags = instrument.collection_request.get_flags()

        user = self.context['user']
        if user and not isinstance(user, AnonymousUser):
            user_max = request_flags['max_instrument_inputs_per_user']
            if user_max is not None:
                existing_inputs = manager.filter_for_context(**self.context)
                input_count = existing_inputs.count()
                if input_count >= user_max:
                    return False

        total_max = request_flags['max_instrument_inputs']
        if total_max is not None:
            no_user_context = self.context.copy()
            no_user_context.pop('user')
            existing_inputs = manager.filter_for_context(**no_user_context)
            input_count = existing_inputs.count()
            if input_count >= total_max:
                return False

        return True

    def clean_data(self, instrument, data):
        """ Cleans the block of input data for storage. """

        # Ensure ResponsePolicy flags are respected
        policy_flags = instrument.response_policy.get_flags()

        disallow_custom = policy_flags['restrict']
        allows_multiple = policy_flags['multiple']
        if allows_multiple and not isinstance(data, list):
            data = [data]
        if not allows_multiple and isinstance(data, list):
            raise ValidationError("Multiple inputs are not allowed")

        allowed_values = None
        if disallow_custom:
            allowed_values = set(instrument.suggested_responses.values_list('data', flat=True))

        # Process each bit in the input, forcing a list in case there is only one
        is_plural = isinstance(data, list)
        if not is_plural:
            data = [data]
        for i, item in enumerate(data):
            data[i] = self.clean_input(instrument, item, allowed_values)
        if not is_plural:
            data = data[0]

        return data

    def clean_input(self, instrument, data, allowed_values=None):
        """
        Cleans a single input data point for storage, either directly or within a list of plural
        inputs (if ``response_policy.multiple`` allows it).
        """

        # Ensure {'_suggested_response': pk} is swapped out for real underlying data
        data = utils.replace_data_for_suggested_responses(instrument, data)

        # Let the method clean and do type coercion with a concrete data reference
        method = self.get_method(instrument)
        data = method.clean(data)

        # Enforce the disallow_custom flag from clean_data()
        if allowed_values and not matchers.all_suggested(data, allowed_values):
            raise ValidationError("Input %r is not from the list of suggested responses" % (data,))

        return data

    def serialize_data(self, data):
        """ Coerces ``data`` for storage on the active input model (CollectedInput or swapped). """
        return data

    def deserialize_data(self, data):
        """
        Coerces retrieved ``data`` from the active input model (CollectedInput or swapped) to an
        appropriate object for its type.
        """
        return data

    # Data-altering methods
    def store(self, instrument, data, instance=None, **model_field_values):
        """
        Creates a new CollectedInput instance for the given data.  Any additional kwargs are sent to
        the manager's ``create()`` method, in case the CollectedInput model has been swapped and
        requires additional fields to successfully save.
        """

        from .. import models
        CollectedInput = models.get_input_model()

        db_data = self.serialize_data(data)

        kwargs = {
            'instrument': instrument,
            'data': db_data,

            # Disallow data integrity funnybusiness
            'collection_request': instrument.collection_request,
        }
        kwargs.update(model_field_values)

        pk = None
        if instance is not None:
            pk = instance.pk
        instance, created = CollectedInput.objects.update_or_create(pk=pk, defaults=kwargs)

        return instance

    def remove(self, instrument, instance):
        """ Removes a given CollectedInput from the instrument. """
        instance.delete()


class Collector(BaseCollector):
    group = 'default'


class BaseAPICollector(Collector):
    __noregister__ = True  # Perpetuate the registration opt-out for this alternate base
    specification_class = specifications.BaseAPISpecification
