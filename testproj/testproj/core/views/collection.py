from input.api.restframework import collection

from . import widgets


class PollTemplateViewCollector(collection.RestFrameworkCollector):
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

    def get_widget(self, instrument):
        has_suggested_responses = instrument.suggested_responses.exists()
        policy = instrument.response_policy.get_flags()

        if has_suggested_responses and not policy['restrict']:
            # TODO: This widget should encompass the whole list paradigm, including the suggestions
            return widgets.ListTextOtherWidget()

        if not has_suggested_responses:
            return widgets.LoneTextWidget()

        return super(PollTemplateViewCollector, self).get_widget(instrument)
