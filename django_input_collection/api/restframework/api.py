from django.core.exceptions import PermissionDenied

from rest_framework import viewsets, views
from rest_framework.decorators import action
from rest_framework.response import Response

from . import serializers
from ...collection.collectors import resolve, registry
from ...encoders import CollectionSpecificationJSONEncoder
from ... import models


class CollectorEnabledMixin(object):
    serializer_class = None  # Obtained at runtime via the collector

    def get_serializer_class(self):
        collector = self.get_collector()
        model = self.get_queryset().model
        return collector.get_serializer_class(model)

    def get_serializer_context(self):
        context = super(CollectorEnabledMixin, self).get_serializer_context()
        context['collector'] = self.get_collector()
        return context


    def get_collector(self):
        if not hasattr(self, '_collector'):
            collector_class = self.get_collector_class()
            kwargs = self.get_collector_kwargs()
            self._collector = collector_class(**kwargs)
        return self._collector

    def get_collector_class(self):
        identifier = self.request.query_params.get('collector')
        try:
            collector_class = resolve(identifier)
        except KeyError:
            raise PermissionDenied('Unknown collector reference')
        return collector_class

    def get_collector_kwargs(self):
        return {
            'collection_request': self.get_collection_request(),
            'group': self.request.query_params.get('group'),
            'context': self.get_collector_context(),
        }

    def get_collector_context(self):
        context = {
            'user': self.request.user,
        }
        return context


class MeasureViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.Measure.objects.all()


class CollectionGroupViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.CollectionGroup.objects.all()


class CollectionRequestViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.CollectionRequest.objects.all()

    @action(detail=True, methods=['get'])
    def specification(self, request, *args, **kwargs):
        collector = self.get_collector()
        response = Response(collector.specification)

        # There's no such thing as a per-response renderer class, so here we are.  Thanks DRF.
        # The request's accepted_renderer will be pushed to the response in finalize_response()
        request.accepted_renderer.encoder_class = CollectionSpecificationJSONEncoder

        return response


class CollectionInstrumentViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.CollectionInstrument.objects.all()

    def filter_queryset(self, queryset):
        filters = {}
        if 'group' in self.request.query_params:
            group = self.request.query_params['group']
            filters['group'] = group

        queryset = queryset.filter(**filters)
        return queryset



class CollectedInputViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    def get_queryset(self):
        return models.get_input_model().objects.all()

    def _save_and_store_ref(self, serializer):
        serializer.save()
        self._instance = serializer.instance

    perform_create = _save_and_store_ref
    perform_update = _save_and_store_ref

    def _rewrite_full_payload(self, response):
        serializer = self.get_serializer(instance=self._instance, write_mode=False)
        response.data = serializer.data
        return response

    def create(self, request, *args, **kwargs):
        response = super(CollectedInputViewSet, self).create(request, *args, **kwargs)
        return self._rewrite_full_payload(response)

    def update(self, request, *args, **kwargs):
        response = super(CollectedInputViewSet, self).update(request, *args, **kwargs)
        return self._rewrite_full_payload(response)

    def get_serializer(self, *args, **kwargs):
        context_kwargs = {
            'write_mode': kwargs.pop('write_mode', None),
        }

        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context(**context_kwargs)
        return serializer_class(*args, **kwargs)

    def get_serializer_context(self, write_mode=None):
        context = super(CollectedInputViewSet, self).get_serializer_context()

        if write_mode is None and self.request.method in ['PUT', 'POST', 'PATCH']:
            write_mode = True

        if write_mode:
            context['write_mode'] = write_mode

        return context


class CollectorRegistryView(views.APIView):
    def get(self, request, *args, **kwargs):
        return Response({
            uid: '.'.join([cls.__module__, cls.__name__]) for uid, cls in sorted(registry.items())
        })
