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
    widget_template_name = None
    option_template_name = None

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

    def update_field(self, field, instrument, *forward_attrs, **attrs):
        self.copy_attrs(field, *forward_attrs, **attrs)

        choices = list(instrument.suggested_responses.values_list('id', 'data'))
        if choices:
            field.choices = choices

    def update_widget(self, field, widget, instrument, *forward_attrs, **attrs):
        choices = getattr(field, 'choices', ())
        use_default_choices = 'choices' not in (forward_attrs + tuple(attrs.keys()))
        if use_default_choices and choices:
            attrs['choices'] = list(choices)

        self.copy_attrs(widget, *forward_attrs, **attrs)

    def serialize(self, instrument):
        data = super(FormFieldWidget, self).serialize(instrument)

        # Remove hard reference to class and create a reasonable serialization here
        data.pop('formfield', None)

        field = self.get_formfield()

        # Update field/widget to spec
        self.update_field(field, instrument, **{
            'template_name': data['template_name'],
        })
        self.update_widget(field, field.widget, instrument, **{
            'template_name': data['widget_template_name'],
            'option_template_name': data['option_template_name'],
        })

        # Main serialization
        field_attrs = ['max_length', 'min_length', 'empty_values', 'help_text', 'input_formats',
                       'choices']
        for attr in field_attrs:
            if not hasattr(field, attr):
                continue
            data[attr] = getattr(field, attr)


        # Get final widget DOM attrs
        data['attrs'] = field.widget.build_attrs(field.widget.attrs, field.widget_attrs(field.widget))
        if hasattr(field, 'choices'):
            data['attrs']['multiple'] = getattr(field.widget, 'allow_multiple_selected', False)

        # Apply early string formatting to values where possible
        dom_attrs_context = {
            'instrument': instrument,
        }
        for k, v in data['attrs'].items():
            if isinstance(v, str):
                data['attrs'][k] = v.format(**dom_attrs_context)

        # Do a server render of widget to store on the serialization
        data['template'] = field.widget.render(**{
            'name': 'instrument-%s' % (instrument.id),
            'value': None,
            'attrs': data['attrs'],
        })

        # Extra
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
    widget_template_name = None
    option_template_name = None

    def get_form(self):
        return self.form_class()

    def serialize(self, instrument):
        data = super(FormWidget, self).serialize(instrument)
        data.pop('form_class', None)

        form = self.get_form()
        data['fields'] = {}
        widget_templates = data['widget_template_name'] or {}
        option_templates = data['option_template_name'] or {}
        for name, field in form.fields.items():
            sub_widget = FormFieldWidget(**{
                'formfield': field,
                'widget_template_name': widget_templates.get(name),
                'option_template_name': option_templates.get(name),
            })
            data['fields'][name] = sub_widget.serialize(instrument)

        if data['template_name']:
            data['template'] = render_to_string(data['template_name'], context={
                'form': form,
                'fields': data['fields'],
            })

        data['meta'].update({
            'form_class': form.__class__.__name__,
        })

        return data
