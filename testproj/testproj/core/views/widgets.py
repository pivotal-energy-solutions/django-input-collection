from django import forms

from input.collection import widgets


lone_input_attrs = {
    'class': 'form-control',
    'placeholder': '(Enter answer)',
}
list_input_other_attrs = {
    'id': 'instrument-{instrument.id}-other',
    'class': 'form-control list-group-item',
    'placeholder': '(Please specify)',
}


# Simple Field version
LIST_FIELD_TEMPLATE_NAME = 'poll/widgets/list_field.html'

# Complex Form version
LIST_FORM_TEMPLATE_NAME = 'poll/widgets/list_form.html'
LIST_WIDGET_TEMPLATE_NAME = 'poll/widgets/list_choices.html'
LIST_OPTION_TEMPLATE_NAME = 'poll/widgets/list_option.html'


# Open response
class LoneTextWidget(widgets.FormFieldWidget):
    formfield = forms.CharField(widget=forms.TextInput(attrs=lone_input_attrs))


# Multiple choice
class ListChoiceSingleWidget(widgets.FormFieldWidget):
    formfield = forms.CharField(widget=forms.RadioSelect)
    widget_template_name = LIST_FIELD_TEMPLATE_NAME
    option_template_name = LIST_OPTION_TEMPLATE_NAME


# Multiple choice, multiple selection
class ListChoiceMultipleWidget(widgets.FormFieldWidget):
    formfield = forms.CharField(widget=forms.CheckboxSelectMultiple)
    widget_template_name = LIST_FIELD_TEMPLATE_NAME
    option_template_name = LIST_OPTION_TEMPLATE_NAME


# Multiple choice with 'Other'
class ListChoiceSingleOtherForm(forms.Form):
    suggested_responses = forms.CharField(widget=forms.RadioSelect)
    custom = forms.CharField(widget=forms.TextInput(attrs=list_input_other_attrs))


class ListChoiceSingleOtherWidget(widgets.FormWidget):
    form_class = ListChoiceSingleOtherForm
    template_name = LIST_FORM_TEMPLATE_NAME
    widget_template_name = {
        'suggested_responses': LIST_WIDGET_TEMPLATE_NAME,
    }
    option_template_name = {
        'suggested_responses': LIST_OPTION_TEMPLATE_NAME,
    }


# Multiple choice with 'Other', multiple selection
class ListChoiceMultipleOtherForm(forms.Form):
    suggested_responses = forms.CharField(widget=forms.CheckboxSelectMultiple)
    custom = forms.CharField(widget=forms.TextInput(attrs=list_input_other_attrs))


class ListChoiceMultipleOtherWidget(widgets.FormWidget):
    form_class = ListChoiceMultipleOtherForm
    template_name = LIST_FORM_TEMPLATE_NAME
    widget_template_name = {
        'suggested_responses': LIST_WIDGET_TEMPLATE_NAME,
    }
    option_template_name = {
        'suggested_responses': LIST_OPTION_TEMPLATE_NAME,
    }
