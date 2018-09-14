from rest_framework import serializers

from ... import models


class ReadWriteToggleMixin(object):
    # FIXME: This strategy deserves to be revisited without the 'exclude' logic being central

    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})
        write_mode = context.pop('write_mode', False)

        super(ReadWriteToggleMixin, self).__init__(*args, **kwargs)

        if write_mode:
            exclude = getattr(self.Meta, 'exclude_write', [])
            for name in exclude_fields:
                del self.fields[name]


class MeasureSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = models.Measure
        fields = '__all__'


class CollectionGroupSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = models.CollectionGroup
        fields = '__all__'


class CollectionRequestSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = models.CollectionRequest
        fields = '__all__'


class CollectionInstrumentSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = models.CollectionInstrument
        fields = '__all__'


class CollectionInputSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = models.get_input_model()
        fields = '__all__'
        exclude_write = ('collection_request',)
