from rest_framework import serializers

from ... import models


class MeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Measure
        fields = '__all__'


class CollectionGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CollectionGroup
        fields = '__all__'


class CollectionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CollectionRequest
        fields = '__all__'


class CollectionInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CollectionInstrument
        fields = '__all__'


class CollectionInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.get_input_model()
        fields = '__all__'
