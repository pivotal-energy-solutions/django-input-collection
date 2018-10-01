from django_input_collection.views import CollectorView

from . import collection


class PollView(CollectorView):
    template_name = 'poll.html'
    collector_class = collection.PollTemplateViewCollector
