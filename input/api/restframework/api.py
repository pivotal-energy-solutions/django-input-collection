from rest_framework import viewsets
from rest_framework.decorators import action

from . import serializers
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
        if 'group' in self.request.query_params:
            group = self.request.query_params['group']
            queryset = queryset.filter(group=group)
        return queryset


CollectionInput = models.get_input_model()

class CollectionInputViewSet(viewsets.ModelViewSet):
    queryset = CollectionInput.objects.all()
    serializer_class = serializers.CollectionInputSerializer
