from inspect import isclass

from django.template.loader import render_to_string

from .base import InputMethod

__all__ = ['FormFieldWidget', 'FormWidget']


class FormFieldWidget(InputMethod):
    """
    Requests input through an HTML-rendered Django field, returns a single python object
    representing the cleaned result.
    """

    formfield = None
    template_name = None

    def get_formfield(self):
        if isclass(self.formfield):
            return self.formfield()
        return self.formfield

    def copy_attrs(self, target, *forward_attrs, **attrs):
        # Look up values for simple attribute names
        for attr in forward_attrs:
            if attr not in attrs:
                attrs[attr] = self.data[attr]

        # Set attributes on instance
        for attr, value in attrs.items():
            if value is not None:  # Avoid clearing good defaults with None values
                setattr(target, attr, value)



    def serialize(self, instrument):
        data = super(FormFieldWidget, self).serialize(instrument)

        # Remove hard reference to class and create a reasonable serialization here
        data.pop('formfield', None)

        field = self.get_formfield()

        choices = list(instrument.suggested_responses.values_list('id', 'data'))
        if choices:
            field.choices = choices

        known_attrs = ['max_length', 'min_length', 'empty_values', 'help_text', 'input_formats',
                       'choices']
        for attr in known_attrs:
            if not hasattr(field, attr):
                continue
            data[attr] = getattr(field, attr)

        dom_attrs_context = {
            'instrument': instrument,
        }
        dom_attrs = field.widget.build_attrs(field.widget.attrs, field.widget_attrs({}))
        for k, v in dom_attrs.items():
            dom_attrs[k] = v.format(**dom_attrs_context)
        data.update({
            'html': field.widget.render(**{
                'name': 'instrument-%s' % (instrument.id),
                'value': None,
                'attrs': dom_attrs,
            }),
        })

        data['meta'].update({
            'widget_class': field.widget.__class__.__name__,
            'field_class': field.__class__.__name__,
        })

        return data

    def clean(self, result):
        """ Let the formfield try to validate it. """
        field = self.get_formfield()
        return field.clean(result)


class FormWidget(InputMethod):
    """ Requests input through an HTML-rendered Django form, returns a dict of cleaned_data. """

    # NOTE: This collects multiple data points for a SINGLE CollectionInstrument, and would
    # therefore potentially expect all data points to be stored in a SINGLE CollectedInput.  A more
    # sophisticated CollectedInput user model would need to be swapped in to handle that.
    # Alternately, data points could be divided and multiple CollectedInputs created for each part
    # if the save() process is built to allow a sane representation of those disparate data points.

    form_class = None
    template_name = None

    def get_form(self):
        return self.form_class()

    def serialize(self, instrument):
        data = super(FormWidget, self).serialize(instrument)
        data.pop('form_class', None)

        form = self.get_form()
        data['fields'] = {}
        for name, field in form.fields.items():
            sub_widget = FormFieldWidget(formfield=field)
            data['fields'][name] = sub_widget.serialize(instrument)

        if self.template_name:
            data['html'] = render_to_string(self.template_name, context={
                'form': form,
                'fields': data['fields'],
            })

        data['meta'].update({
            'form_class': form.__class__.__name__,
        })

        return data
