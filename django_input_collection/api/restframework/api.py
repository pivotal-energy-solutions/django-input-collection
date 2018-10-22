from rest_framework import viewsets, views
from rest_framework.decorators import action
from rest_framework.response import Response

from . import serializers
from ...collection.collectors import registry
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

    def get_serializer_context(self):
        context = super(CollectedInputViewSet, self).get_serializer_context()

        if self.request.method in ['PUT', 'POST']:
            context['write_mode'] = True

        return context


class CollectorRegistryView(views.APIView):
    def get(self, request, *args, **kwargs):
        return Response({
            uid: '.'.join([cls.__module__, cls.__name__]) for uid, cls in sorted(registry.items())
        })
