import importlib
import hashlib
from inspect import isclass
import json

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from ..encoders import CollectionSpecificationJSONEncoder
from .. import models
from . import utils
from . import specifications
from . import methods

__all__ = ['resolve', 'Collector', 'BaseAPICollector']


CollectedInput = models.get_input_model()

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
    raise CollectorRegistrationException(msg % {'cls': cls})


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
        fail_registration_action("Collector %(cls)r with __noregister__=True cannot be inspected for a registration identifier.")

class Collector(object, metaclass=CollectorType):
    __version__ = (0, 0, 0, 'dev')
    def fail_register(cls):
        fail_registration_action("Collector %(cls)r with __noregister__=True cannot be registered.")
        

    specification_class = specifications.Specification
    group = 'default'

    # TODO: Streamline how this will have to work for targetting response_policy settings, too.
    # I think it'll have to be something like a list of "match dicts" and the first one to match
    # all settings for the instrument will be used.
    type_methods = None
    measure_methods = None

    def __init__(self, collection_request, group='default', **context):
        self.collection_request = collection_request
        self.context = context
        self.group = group

        self.type_methods = self.get_type_methods()
        self.measure_methods = self.get_measure_methods()

        registry.setdefault(cls.get_identifier(), cls)


    # Resolution utils
    def get_specification(self):
        return self.specification_class(self)

    def get_type_methods(self):
        if not hasattr(self, '_type_methods'):
            self._type_methods = self.type_methods or {}
        return self._type_methods

    def get_measure_methods(self):
        if not hasattr(self, '_measure_methods'):
            self._measure_methods = self.measure_methods or {}
        return self._measure_methods

    def get_method_kwargs(self, instrument):
        kwargs = {
            
        }
        return kwargs

    def get_method(self, instrument):
        method = methods.InputMethod

        if instrument.measure_id in self.measure_methods:
            method = self.measure_methods[instrument.measure_id]
        elif instrument.type_id in self.type_methods:
            method = self.type_methods[instrument.type_id]

        if isclass(method):
            method = method()

        method_kwargs = self.get_method_kwargs(instrument)
        method.update_kwargs(**method_kwargs)

        return method

    # Main properties
    @property
    def specification(self):
        serializer = self.get_specification()
        return serializer.data

    @property
    def specification_json(self):
        return json.dumps(self.specification, cls=CollectionSpecificationJSONEncoder)

    ## Instrument/Input runtime hooks
    def is_instrument_allowed(self, instrument):
        """
        Returns True when the given instrument passes all related conditions limiting its use.
        """
        return instrument.test_conditions(**self.context)

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
        """
        Return cleaned/validated data based on a speculative input ``data``.  Data coded for
        representing SuggestedResponse instance ids are translated to the concrete data that
        SuggestedResponse implies, thus making the final data safe to send for serialization and
        storage on the active CollectedInput model.
        """

        # Ensure ResponsePolicy flags are respected
        policy_flags = instrument.response_policy.get_flags()

        allow_multiple = policy_flags['multiple']
        if not allow_multiple and isinstance(data, list):
            raise ValidationError("Multiple inputs are not allowed")

        disallow_custom = policy_flags['restrict']

        # Clean coded ids if needed
        suggested_values = set(instrument.suggested_responses.values_list('data', flat=True))
        if suggested_values:
            is_single = (not policy_flags['multiple'])

            if is_single:
                data = [data]

            if disallow_custom and not utils.matchers.all_suggested(data, suggested_values):
                raise ValidationError("Inputs must be chosen from the suggested responses")

            data = utils.get_data_for_suggested_responses(instrument, *data)

            if is_single:
                data = data[0]

        # Let the method clean and do type coercion
        method = self.get_method(instrument)
        data = method.clean(data)

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


class BaseAPICollector(Collector):
    __noregister__ = True

    specification_class = specifications.BaseAPISpecification
