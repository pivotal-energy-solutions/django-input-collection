from inspect import isclass

from django.template.loader import render_to_string

from .base import InputMethod

__all__ = ['FormFieldMethod', 'FormMethod']


class FormFieldMethod(InputMethod):
    """
    Requests input through an HTML-rendered Django field, returns a single python object
    representing the cleaned result.
    """

    formfield = None
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

    def get_data(self, instrument):
        data = super(FormFieldMethod, self).get_data(instrument)

        field = self.get_formfield()
        data['formfield'] = field

        # Update field/widget to spec
        self.update_field(field, instrument)
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

        # Extra
        data['meta'].update({
            'widget_class': '.'.join([field.widget.__module__, field.widget.__class__.__name__]),
            'field_class': '.'.join([field.__module__, field.__class__.__name__]),
        })

        return data

    def render(self, data, field, context):
        content = field.widget._render(field.widget.template_name, context)
        return content

    def serialize(self, instrument):
        data = super(FormFieldMethod, self).serialize(instrument)

        field = data.pop('formfield')  # Don't want this to go through to final serialization
        field_name = 'instrument-%s' % (instrument.id)
        field_value = None
        context = field.widget.get_context(field_name, field_value, data['attrs'])
        context['method'] = data
        data['template'] = self.render(data, field, context)

        return data

    def clean(self, result):
        """ Clean result via ``formfield.clean()``. """
        field = self.get_formfield()
        return field.clean(result)


class FormMethod(InputMethod):
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

    field_input_method_class = FormFieldMethod

    def get_form(self):
        return self.form_class()

    def get_data(self, instrument):
        data = super(FormMethod, self).get_data(instrument)

        data.pop('form_class', None)
        form = self.get_form()
        data['form'] = form

        data['fields'] = {}
        widget_templates = data['widget_template_name'] or {}
        option_templates = data['option_template_name'] or {}
        for name, field in form.fields.items():
            sub_method = FormFieldMethod(**{
                'formfield': field,
                'widget_template_name': widget_templates.get(name),
                'option_template_name': option_templates.get(name),
            })
            data['fields'][name] = sub_method.serialize(instrument)

        data['meta'].update({
            'form_class': '.'.join([form.__module__, form.__class__.__name__]),
        })

        return data

    def render(self, data, form, context):
        if data['template_name']:
            return render_to_string(data['template_name'], context=context)
        return None

    def serialize(self, instrument):
        data = super(FormMethod, self).serialize(instrument)

        form = data.pop('form')
        context = {
            'form': form,
            'fields': data['fields'],
        }
        data['template'] = self.render(data, form, context)

        return data
