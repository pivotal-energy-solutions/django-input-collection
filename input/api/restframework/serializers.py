from rest_framework import serializers

from ... import models


class MeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Measure


class CollectionGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CollectionGroup


class CollectionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CollectionRequest


class CollectionInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CollectionInstrument


class CollectionInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.get_input_model()
