import json

from django.views.generic import DetailView
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator

from .json import ModelJSONEncoder
from . import models


class CollectorView(DetailView):
    model = models.CollectionRequest
    collector_class = None

    dispatch = method_decorator(ensure_csrf_cookie)(DetailView.dispatch)

    def get_collector_kwargs(self, **kwargs):
        kwargs.update({
            'collection_request': self.object,
            'user': self.request.user,
        })
        return kwargs

    def get_collector_class(self):
        return self.collector_class

    def get_collector(self):
        collector_class = self.get_collector_class()
        collector_kwargs = self.get_collector_kwargs()
        collector = collector_class(**collector_kwargs)
        return collector

    def get_context_data(self, **kwargs):
        context = super(CollectorView, self).get_context_data(**kwargs)

        collector = self.get_collector()

        context['payload'] = collector.info
        context['payload_json'] = json.dumps(collector.info, cls=ModelJSONEncoder)

        return context
