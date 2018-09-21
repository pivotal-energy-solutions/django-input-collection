from .base import InputMethod

__all__ = ['FormWidget', 'FormFieldWidget']


class FormWidget(InputMethod):
    """ Requests input through an HTML-rendered Django form, returns a dict of cleaned_data. """

    # NOTE: This collects multiple data points for a SINGLE CollectionInstrument, and would
    # therefore potentially expect all data points to be stored in a SINGLE CollectedInput.  A more
    # sophisticated CollectedInput user model would need to be swapped in to handle that.
    # Alternately, data points could be divided and multiple CollectedInputs created for each part
    # if the save() process is built to allow a sane representation of those disparate data points.

    form_class = None


class FormFieldWidget(InputMethod):
    """
    Requests input through an HTML-rendered Django field, returns a single python object
    representing the cleaned result.
    """

    formfield_class = None

    def get_formfield(self):
        return self.formfield_class()

    def serialize(self, instrument):
        # NOTE: If we can ensure an easy design where the <input> names don't need to be scoped by
        # the [name="instrument-{pk}"], we could potentially drop this ``instrument`` arg.

        data = super(FormFieldWidget, self).serialize(instrument)

        # Remove hard reference to class and create a reasonable serialization here
        del data['formfield_class']

        field = self.get_formfield()
        known_attrs = ['max_length', 'min_length', 'empty_values', 'help_text', 'input_formats']
        for attr in known_attrs:
            if not hasattr(field, attr):
                continue
            data[attr] = getattr(field, attr)

        data.update({
            'html': field.widget.render(**{
                'name': 'instrument-%s' % (instrument.id),
                'value': None,
                'attrs': field.widget_attrs({}),
            }),
        })

        data['meta'].update({
            'widget_class': field.widget.__class__.__name__,
            'field_class': field.__class__.__name__,
        })

        return data
