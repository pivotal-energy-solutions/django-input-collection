from django import forms

from django_input_collection.collection import methods


lone_input_attrs = {
    'class': 'form-control',
    'name': 'instrument-{instrument.id}',
    'placeholder': '(Enter answer)',
}
list_input_suggested_attrs = {
    'class': 'form-control',
    'name': 'instrument-{instrument.id}',
}
list_input_other_attrs = {
    'id': 'instrument-{instrument.id}-other',
    'class': 'form-control list-group-item',
    'name': 'instrument-{instrument.id}',
    'placeholder': '(Please specify)',
}


# Simple Field version
LIST_FIELD_TEMPLATE_NAME = 'poll/methods/list_field.html'

# Complex Form version
LIST_FORM_TEMPLATE_NAME = 'poll/methods/list_form.html'
LIST_WIDGET_TEMPLATE_NAME = 'poll/methods/list_choices.html'
LIST_OPTION_TEMPLATE_NAME = 'poll/methods/list_option.html'


# Open response
class LoneTextMethod(methods.FormFieldMethod):
    formfield = forms.CharField(widget=forms.TextInput(attrs=lone_input_attrs))


# Multiple choice
class ListChoiceSingleMethod(methods.FormFieldMethod):
    formfield = forms.CharField(widget=forms.RadioSelect(attrs=list_input_suggested_attrs))
    widget_template_name = LIST_FIELD_TEMPLATE_NAME
    option_template_name = LIST_OPTION_TEMPLATE_NAME


# Multiple choice, multiple selection
class ListChoiceMultipleMethod(methods.FormFieldMethod):
    formfield = forms.CharField(widget=forms.CheckboxSelectMultiple(attrs=list_input_suggested_attrs))
    widget_template_name = LIST_FIELD_TEMPLATE_NAME
    option_template_name = LIST_OPTION_TEMPLATE_NAME


# Multiple choice with 'Other'
class ListChoiceSingleOtherForm(forms.Form):
    suggested_responses = forms.CharField(widget=forms.RadioSelect(attrs=list_input_suggested_attrs))
    custom = forms.CharField(widget=forms.TextInput(attrs=list_input_other_attrs))


class ListChoiceSingleOtherMethod(methods.FormMethod):
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
    suggested_responses = forms.CharField(widget=forms.CheckboxSelectMultiple(attrs=list_input_suggested_attrs))
    custom = forms.CharField(widget=forms.TextInput(attrs=list_input_other_attrs))


class ListChoiceMultipleOtherMethod(methods.FormMethod):
    form_class = ListChoiceMultipleOtherForm
    template_name = LIST_FORM_TEMPLATE_NAME
    widget_template_name = {
        'suggested_responses': LIST_WIDGET_TEMPLATE_NAME,
    }
    option_template_name = {
        'suggested_responses': LIST_OPTION_TEMPLATE_NAME,
    }
