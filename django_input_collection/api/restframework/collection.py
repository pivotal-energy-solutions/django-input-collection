from django.urls import reverse

from ...collection import BaseAPICollector, BaseAPISpecification
from ... import models
from . import serializers


class RestFrameworkSpecification(BaseAPISpecification):
    content_type = 'application/json'

    def get_api_info(self):
        info = super(RestFrameworkSpecification, self).get_api_info()

        input_list = reverse('collection-api:input-list')
        input_detail = reverse('collection-api:input-detail', kwargs={'pk': '__id__'})
        instrument_list = reverse('collection-api:instrument-list')
        instrument_detail = reverse('collection-api:instrument-detail', kwargs={'pk': '__id__'})

        info['endpoints'] = {
            'input': {
                'list': {'url': input_list, 'method': 'GET'},
                'add': {'url': input_list, 'method': 'POST'},
                'get': {'url': input_detail, 'method': 'GET'},
            },
            'instrument': {
                'list': {'url': instrument_list, 'method': 'GET'},
                'get': {'url': instrument_detail, 'method': 'GET'},
            },
        }
        return info


class RestFrameworkCollector(BaseAPICollector):
    specification_class = RestFrameworkSpecification

    # rest_framework CollectedInput serializers
    serializer_classes = {}
    base_serializer_classes = {
        'measure': serializers.MeasureSerializer,
        'request': serializers.CollectionRequestSerializer,
        'group': serializers.CollectionGroupSerializer,
        'instrument': serializers.CollectionInstrumentSerializer,
        'input': serializers.CollectedInputSerializer,
    }
    serializer_codenames = {
        models.Measure: 'measure',
        models.CollectionRequest: 'request',
        models.CollectionGroup: 'group',
        models.CollectionInstrument: 'instrument',
        models.get_input_model(): 'input',
    }

    def get_serializer_class(self, model):
        codename = self.serializer_codenames[model]
        return self.serializer_classes.get(codename, self.base_serializer_classes[codename])

    def validate(self, instrument, data):
        """ Raises any validation errors in the serializer's ``data``. """
        return data
