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

    def serialize(self):
        data = super(FormFieldWidget, self).serialize()

        field = self.get_formfield()
        info = {
            'default_error_messages': field.default_error_messages,
            'empty_values': field.empty_values,
            'help_text': field.empty_values,
            'widget_attrs': field.widget_attrs({}),
        }

        data['formfield_class'] = info
        return data
