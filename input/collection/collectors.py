from inspect import isclass
import json

from django.contrib.auth.models import AnonymousUser

from ..encoders import CollectionSpecificationJSONEncoder
from .base import get_data_for_suggested_responses
from . import specifications
from . import widgets


class Collector(object):
    __version__ = (0, 0, 0, 'dev')
    group = 'default'
    type_widgets = None
    measure_widgets = None
    specification_class = specifications.Specification

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
        return json.dumps(self.specification, cls=CollectionSpecificationJSONEncoder)

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
    specification_class = specifications.BaseAPISpecification
