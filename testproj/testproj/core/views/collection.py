from django import forms

from input.api.restframework import collection
from input.collection import widgets


class PollTemplateViewCollector(collection.RestFrameworkCollector):
    measure_widgets = {
        'measure-0': widgets.FormFieldWidget(formfield_class=forms.IntegerField),
    }

    @property
    def specification(self):
        specification = super(PollTemplateViewCollector, self).specification

        # The default Django template language stuff makes it impossible to look up an index, so
        # this saves us the heartache of trying.
        specification['instruments_info']['ordered_instruments'] = [
            specification['instruments_info']['instruments'][id] for id in specification['instruments_info']['ordering']
        ]

        # More shorthand for easily displaying ALL instruments, not just top-level
        specification['instruments_info']['all_ordered_instruments'] = list(
             sorted(specification['instruments_info']['instruments'].values(), key=lambda info: info['order'])
        )
        return specification
