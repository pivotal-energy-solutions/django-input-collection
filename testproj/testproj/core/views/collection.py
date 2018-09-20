from input.api.restframework import collection


class PollTemplateViewCollector(collection.RestFrameworkCollector):
    @property
    def info(self):
        info = super(PollTemplateViewCollector, self).info

        # The default Django template language stuff makes it impossible to look up an index, so
        # this saves us the heartache of trying.
        info['instruments_info']['ordered_instruments'] = [
            info['instruments_info']['instruments'][id] for id in info['instruments_info']['ordering']
        ]
        return info
