from rest_framework import serializers

from ... import models, collection


class ReadWriteToggleMixin(object):
    # FIXME: This strategy deserves to be revisited without the 'exclude' logic being central

    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})
        write_mode = context.pop('write_mode', False)

        super(ReadWriteToggleMixin, self).__init__(*args, **kwargs)

        if write_mode:
            exclude_fields = getattr(self.Meta, 'exclude_write', [])
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
        fields = ['collection_request', 'measure', 'group', 'type', 'order', 'text', 'description',
                  'help', 'response_policy', 'suggested_responses', 'collectedinput_set']


CollectedInput = models.get_input_model()

class CollectedInputSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = CollectedInput
        fields = '__all__'
        exclude_write = ('collection_request',)

    def validate(self, data):
        instrument = data['instrument']

        context = {
            'user': self.context['request'].user,
        }

        at_capacity = (not self.allows_new_input(instrument, **context))
        if at_capacity:
            raise serializers.ValidationError("[CollectionInstrument=%r] No new inputs allowed. (user=%r, data=%r)" % (
                instrument.pk,
                context['user'],
                data['data'],
            ))

        if instrument.suggested_responses.exists():
            try:
                data['data'] = self.transform_responses_to_data(instrument, data['data'], **context)
            except ValueError as e:
                raise serializers.ValidationError(str(e))

        return data

    # Validation helpers
    def allows_new_input(self, instrument, **context):
        return CollectedInput.allowed_for_instrument(instrument, **context)

    def transform_responses_to_data(self, instrument, responses, **context):
        return CollectedInput.clean_data_for_instrument(instrument, responses, **context)

    def create(self, validated_data):
        return collection.store(instance=None, **validated_data)

    def update(self, instance, validated_data):
        return collection.store(instance=instance, **validated_data)
