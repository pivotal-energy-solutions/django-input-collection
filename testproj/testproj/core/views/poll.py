from input.views import CollectorView

from . import collectors


class PollView(CollectorView):
    template_name = 'poll.html'
    collector_class = collectors.PollCollector
