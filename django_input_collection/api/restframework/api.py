from django.core.exceptions import PermissionDenied

from rest_framework import viewsets, views
from rest_framework.decorators import action
from rest_framework.response import Response

from . import serializers
from ...collection.collectors import resolve, registry
from ...encoders import CollectionSpecificationJSONEncoder
from ... import models


class MeasureViewSet(viewsets.ModelViewSet):
    queryset = models.Measure.objects.all()
    serializer_class = serializers.MeasureSerializer


class CollectionGroupViewSet(viewsets.ModelViewSet):
    queryset = models.CollectionGroup.objects.all()
    serializer_class = serializers.CollectionGroupSerializer


class CollectionRequestViewSet(viewsets.ModelViewSet):
    queryset = models.CollectionRequest.objects.all()
    serializer_class = serializers.CollectionRequestSerializer

    @action(detail=True, methods=['get'])
    def specification(self, request, *args, **kwargs):
        identifier = request.query_params.get('collector')
        try:
            collector_class = resolve(identifier)
        except KeyError:
            raise PermissionDenied('Unknown collector reference')

        group = request.query_params.get('group')
        context = {
            'user': request.user,
        }
        instance = self.get_object()
        collector = collector_class(instance, group=group, **context)
        response = Response(collector.specification)

        # There's no such thing as a per-response renderer class, so here we are.  Thanks DRF.
        # The request's accepted_renderer will be pushed to the response in finalize_response()
        request.accepted_renderer.encoder_class = CollectionSpecificationJSONEncoder

        return response


class CollectionInstrumentViewSet(viewsets.ModelViewSet):
    queryset = models.CollectionInstrument.objects.all()
    serializer_class = serializers.CollectionInstrumentSerializer

    def filter_queryset(self, queryset):
        filters = {}
        if 'group' in self.request.query_params:
            group = self.request.query_params['group']
            filters['group'] = group

        queryset = queryset.filter(**filters)
        return queryset


class CollectedInputViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.CollectedInputSerializer

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
