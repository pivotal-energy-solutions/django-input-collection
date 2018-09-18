import json

from django.views.generic import DetailView

from .json import ModelJSONEncoder
from . import models


class CollectorView(DetailView):
    model = models.CollectionRequest
    collector_class = None

    def get_collector_class(self):
        return self.collector_class

    def get_collector_kwargs(self, **kwargs):
        kwargs.update({
            'collection_request': self.object,
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(CollectorView, self).get_context_data(**kwargs)

        collector_class = self.get_collector_class()
        collector_kwargs = self.get_collector_kwargs()
        collector = collector_class(**collector_kwargs)

        context['payload'] = collector.info
        context['payload_json'] = json.dumps(collector.info, cls=ModelJSONEncoder)

        return context
