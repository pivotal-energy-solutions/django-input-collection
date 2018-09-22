from django import forms

from input.collection import widgets


lone_input_classes = ' '.join(['form-control'])
list_input_classes = ' '.join(['form-control', 'list-group-item'])

lone_input_attrs = {
    'class': lone_input_classes,
    'placeholder': '(Enter answer)',
}
list_input_attrs = {'class': list_input_classes}
list_input_other_attrs = dict(list_input_attrs, **{
    'id': 'instrument-{instrument.id}-other',
    'placeholder': '(Please specify)',
})

class LoneTextWidget(widgets.FormFieldWidget):
    formfield = forms.CharField(widget=forms.TextInput(attrs=lone_input_attrs))


class ListTextOtherWidget(widgets.FormFieldWidget):
    formfield = forms.CharField(widget=forms.TextInput(attrs=list_input_other_attrs))
