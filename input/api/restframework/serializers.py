from django.core.exceptions import PermissionDenied

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

    def to_representation(self, obj):
        # restframework is so impossible to customize for this behavior anywhere else.  The
        # inefficiency of having to do the normal behavior and then overwrite it with additional
        # queries bothers me a lot.  Help.  I've tried everything.
        data = super(CollectionInstrumentSerializer, self).to_representation(obj)
        data['collectedinput_set'] = self.patch_collectedinput_set_data(obj)
        return data

    def patch_collectedinput_set_data(self, obj):
        # The logic I wish I could just put on a custom field and have it respected in a plural data
        # situation.  ``Meta.list_serializer_class`` has no control because ManyRelatedField is not
        # a ListSerializer.
        context = {
            'user': self.context['request'].user,
        }
        queryset = obj.collectedinput_set(manager='filtered_objects').filter_for_context(**context)
        pklist_field = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
        return pklist_field.to_representation(queryset)


class RegisteredCollectorField(serializers.Field):
    def to_internal_value(self, identifier):
        return collection.Collector.resolve(identifier)


CollectedInput = models.get_input_model()

class CollectedInputSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = CollectedInput
        fields = '__all__'
        exclude_write = ('collection_request', 'user')

    def get_fields(self):
        fields = super(CollectedInputSerializer, self).get_fields()
        fields['collector'] = RegisteredCollectorField(write_only=True)
        return fields

    def validate(self, data):
        instrument = data['instrument']

        user = self.context['request'].user
        data['user'] = user

        context = {
            'user': user,
        }
        collector_class = data.pop('collector')  # 'collector' won't be a valid model field
        self.collector = collector_class(instrument.collection_request, **context)

        is_unavailable = (not self.collector.is_instrument_allowed(instrument))
        if is_unavailable:
            raise PermissionDenied("[CollectionInstrument=%r] Availability conditions failed. (user=%r, data=%r)" % (
                instrument.pk,
                context['user'],
                data['data'],
            ))

        at_capacity = (not self.collector.is_input_allowed(instrument))
        if at_capacity:
            raise PermissionDenied("[CollectionInstrument=%r] No new inputs allowed. (user=%r, data=%r)" % (
                instrument.pk,
                context['user'],
                data['data'],
            ))

        try:
            data['data'] = self.collector.clean_data(instrument, data['data'])
        except ValueError as e:
            raise serializers.ValidationError(str(e))

        return data

    # Validation helpers
    def create(self, validated_data):
        return collection.store(instance=None, **validated_data)

    def update(self, instance, validated_data):
        return collection.store(instance=instance, **validated_data)
