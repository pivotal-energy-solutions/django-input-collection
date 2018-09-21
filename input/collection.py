from collections import defaultdict
from inspect import isclass
import json

from django.forms.models import model_to_dict

from .json import CollectionSpecificationJSONEncoder
from . import models
from . import widgets

__all__ = ['Collector', 'store']


def store(instrument, data, instance=None, **model_kwargs):
    """
    Creates a new CollectedInput instance for the given data.  Any additional kwargs are sent to
    the manager's ``create()`` method, in case the CollectedInput model has been swapped and
    requires additional fields to successfully save.
    """
    CollectedInput = models.get_input_model()

    db_data = CollectedInput().serialize_data(data)  # FIXME: classmethod/staticmethod?

    kwargs = {
        'instrument': instrument,
        'data': db_data,

        # Disallow data integrity funnybusiness
        'collection_request': instrument.collection_request,
    }
    kwargs.update(model_kwargs)

    pk = None
    if instance is not None:
        pk = instance.pk
    instance, created = CollectedInput.objects.update_or_create(pk=pk, defaults=kwargs)

    return instance


def get_data_for_suggested_responses(instrument, *responses):
    class missing:
        pass

    values = []

    lookups = dict(instrument.suggested_responses.values_list('id', 'data'))
    for response in responses:
        data = response  # Assume raw passthrough by default

        # Transform data referring to a SuggestedResponse id
        if isinstance(data, dict):
            suggested_response_id = data.get('_suggested_response', missing)
            if suggested_response_id is not missing:
                try:
                    suggested_response_id = int(suggested_response_id)
                except ValueError as e:
                    pass  # It's going to raise again shortly anyway with a better message

                # Verify the coded SuggestedResponse id is valid for this instrument
                data = lookups.get(suggested_response_id, missing)
                if data is missing:
                    raise ValueError("[CollectionInstrument id=%r] Invalid SuggestedResponse id=%r in choices: %r" % (
                        instrument.id,
                        suggested_response_id,
                        lookups,
                    ))

        values.append(data)

    return values


class Specification(object):
    __version__ = (0, 0, 0, 'dev')

    def __init__(self, collector):
        self.collector = collector

    @property
    def data(self):
        """ Returns a JSON-safe spec for another tool to correctly supply inputs. """
        meta_info = self.get_meta()
        collection_request_info = model_to_dict(self.collector.collection_request)
        inputs_info = self.get_collected_inputs_info()
        instruments_info = self.get_instruments_info(inputs_info)

        info = {
            'meta': meta_info,
            'collection_request': collection_request_info,
            'group': self.collector.group,
            'instruments_info': instruments_info,
            'collected_inputs': inputs_info,
        }
        return info

    def get_meta(self):
        return {
            'version': self.collector.__version__,
            'serializer_version': self.__version__,
        }

    def get_instruments_info(self, inputs_info=None):
        ordering = list(self.collector.collection_request.collectioninstrument_set \
                                      .filter(conditions=None) \
                                      .values_list('id', flat=True))
        instruments_info = {
            'instruments': {},
            'ordering': ordering,
        }

        if inputs_info is None:
            inputs_info = {}

        queryset = self.collector.collection_request.collectioninstrument_set.all()

        for instrument in queryset:
            info = model_to_dict(instrument, exclude=['suggested_responses'])
            info['response_info'] = self.get_instrument_response_info(instrument)
            info['collected_inputs'] = inputs_info.get(instrument.pk)
            info['conditions'] = [
                self.get_condition_info(condition) for condition in instrument.conditions.all()
            ]
            info['child_conditions'] = [
                self.get_condition_info(condition) for condition in instrument.child_conditions.all()
            ]

            instruments_info['instruments'][instrument.id] = info

        return instruments_info

    def get_condition_info(self, condition):
        condition_info = model_to_dict(condition)

        condition_info['condition_group'] = self.get_condition_group_info(
            condition.condition_group
        )

        return condition_info

    def get_condition_group_info(self, group):
        child_queryset = group.child_groups.prefetch_related('cases')

        group_info = model_to_dict(group)
        group_info['cases'] = list(map(model_to_dict, group.cases.all()))
        group_info['child_groups'] = []
        for child_group in child_queryset:
            group_info['child_groups'].append(
                self.get_condition_group_info(child_group)
            )

        return group_info

    def get_collected_inputs_info(self):
        inputs_info = defaultdict(list)

        queryset = self.collector.collection_request.collectedinput_set(manager='filtered_objects') \
                                                    .filter_for_context(**self.collector.context)
        for input in queryset:
            inputs_info[input.instrument_id].append(model_to_dict(input))

        return inputs_info

    def get_instrument_response_info(self, instrument):
        """ Returns input specifications for data this instruments wants to collect. """
        policy_info = model_to_dict(instrument.response_policy)
        suggested_responses_info = self.get_suggested_responses_info(instrument)
        widget_info = self.get_widget_info(instrument)

        input_info = {
            'response_policy': policy_info,
            'suggested_responses': suggested_responses_info,
            'widget': widget_info,
        }
        return input_info

    def get_suggested_responses_info(self, instrument):
        queryset = instrument.suggested_responses.all()
        suggested_responses_info = list(map(model_to_dict, queryset))
        return suggested_responses_info

    def get_widget_info(self, instrument):
        """
        Resolve a widget for the given instrument based on self.measure_widgets, or
        self.type_widgets, whichever is resolvable first.
        """

        widget = self.collector.get_widget(instrument)
        widget_info = widgets.serialize_widget(widget)
        return widget_info


class BaseAPISpecification(Specification):
    content_type = 'application/json'

    def get_meta(self):
        meta_info = super(BaseAPISpecification, self).get_meta()
        meta_info['api'] = self.get_api_info()
        return meta_info

    def get_api_info(self):
        return {
            'content_type': self.content_type,
            'endpoints': {},
        }


class Collector(object):
    __version__ = (0, 0, 0, 'dev')
    group = 'default'
    type_widgets = None
    measure_widgets = None
    specification_class = Specification

    def __init__(self, collection_request, group='default', **context):
        self.collection_request = collection_request
        self.context = context
        self.group = group

        self.type_widgets = self.get_type_widgets()
        self.measure_widgets = self.get_measure_widgets()

    # Resolution utils
    def get_specification(self):
        return self.specification_class(self)

    def get_type_widgets(self):
        if not hasattr(self, '_type_widgets'):
            self._type_widgets = self.type_widgets or {}
        return self._type_widgets

    def get_measure_widgets(self):
        if not hasattr(self, '_measure_widgets'):
            self._measure_widgets = self.measure_widgets or {}
        return self._measure_widgets

    def get_widget_kwargs(self, instrument):
        kwargs = {
            
        }
        return kwargs

    def get_widget(self, instrument):
        widget = widgets.Widget

        if instrument.measure_id in self.measure_widgets:
            widget = self.measure_widgets[instrument.measure_id]
        elif instrument.type_id in self.type_widgets:
            widget = self.type_widgets[instrument.type_id]

        if isclass(widget):
            widget = widget()

        widget_kwargs = self.get_widget_kwargs(instrument)
        widget.update_kwargs(**widget_kwargs)

        return widget

    # Main properties
    @property
    def specification(self):
        serializer = self.get_specification()
        return serializer.data

    @property
    def specification_json(self):
        return json.dumps(self.specification, cls=CollectionSpecificationJSONEncoder, indent=4)

    # Instrument/Input runtime checks
    def is_instrument_allowed(self, instrument, **context):
        """
        Returns True when the given instrument passes all related conditions limiting its use.
        """
        return instrument.test_conditions(**context)

    def is_input_allowed(self, instrument, **context):
        """
        Returns True when the given instrument passes checks against flags on its CollectionRequest.
        """
        manager = instrument.collectedinput_set(manager='filtered_objects')

        user = context.get('user')
        if user and not isinstance(user, AnonymousUser):
            user_max = instrument.collection_request.max_instrument_inputs_per_user
            if user_max is not None:
                existing_inputs = manager.filter_for_context(**context)
                input_count = existing_inputs.count()
                if input_count >= user_max:
                    return False

        total_max = instrument.collection_request.max_instrument_inputs
        if total_max is not None:
            no_user_context = dict(context, user=None)
            existing_inputs = manager.filter_for_context(**no_user_context)
            input_count = existing_inputs.count()
            if input_count >= total_max:
                return False

        return True

    def clean_data(self, instrument, data, **context):
        """
        Return cleaned/validated data based on a speculative input ``data``.  Data coded for
        representing SuggestedResponse instance ids are translated to the concrete data that
        SuggestedResponse implies, thus making the final data safe to send for serialization and
        storage on the active CollectedInput model.
        """

        # Clean coded ids if needed
        has_suggested_responses = instrument.suggested_responses.exists()
        if has_suggested_responses:
            is_single = (not instrument.response_policy.multiple)

            if is_single:
                data = [data]

            data = get_data_for_suggested_responses(instrument, *data)

            if is_single:
                data = data[0]

        # Let the widget clean and do type coercion
        widget = self.get_widget(instrument)
        data = widget.clean(data)

        return data

    # These default implementations trust the type to match whatever modelfield is in use for the
    # ``data`` field on the concrete model.
    def serialize_data(self, data):
        """ Coerces ``data`` for storage on the active input model (CollectedInput or swapped). """
        return data

    def deserialize_data(self, data):
        """
        Coerces retrieved ``data`` from the active input model (CollectedInput or swapped) to an
        appropriate object for its type.
        """
        return data


class BaseAPICollector(Collector):
    specification_class = BaseAPISpecification
