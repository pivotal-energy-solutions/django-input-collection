from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import AnonymousUser

from rest_framework import serializers

from ... import models, collection


class ReadWriteToggleMixin(object):
    # FIXME: This strategy deserves to be revisited without the 'exclude' logic being central

    def __init__(self, *args, **kwargs):
        context = kwargs.get('context', {})
        write_mode = context.pop('write_mode', False)

        super(ReadWriteToggleMixin, self).__init__(*args, **kwargs)

        if write_mode:
            include_fields = getattr(self.Meta, 'include_write', '__all__')
            exclude_fields = getattr(self.Meta, 'exclude_write', [])

            if include_fields == '__all__':
                include_fields = list(self.fields.keys())

            if include_fields:
                for name in self.fields:
                    if name not in include_fields:
                        del self.fields[name]

            if exclude_fields:
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


class ContextualCollectedInputsSerializer(serializers.Serializer):
    """ Filters the given CollectedInput queryset for the active context. """
    # NOTE: Don't confuse the context sent to the queryset method for the serializer's own attribute
    # with the same name.

    def to_representation(self, queryset):
        collector = self.context['collector']
        queryset = queryset.filter_for_context(**collector.context)
        serializer_class = collector.get_serializer_class(CollectedInput)
        serializer = serializer_class(queryset, many=True, context=self.context)
        return serializer.data


class SuggestedResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SuggestedResponse
        exclude = ['date_created', 'date_modified']

    def to_representation(self, obj):
        data = super(SuggestedResponseSerializer, self).to_representation(obj)
        data['_suggested_response'] = data['id']
        return data


class CollectionInstrumentSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    response_policy = serializers.SerializerMethodField()
    suggested_responses = SuggestedResponseSerializer(many=True, read_only=True)
    collectedinput_set = ContextualCollectedInputsSerializer()

    class Meta:
        model = models.CollectionInstrument
        fields = ['id', 'collection_request', 'measure', 'group', 'type', 'order', 'text',
                  'description', 'help', 'response_policy', 'suggested_responses',
                  'collectedinput_set']

    def get_response_policy(self, instance):
        return instance.response_policy.get_flags()


class RegisteredCollectorField(serializers.Field):
    def to_internal_value(self, identifier):
        try:
            return collection.resolve(identifier)
        except KeyError:
            raise ValidationError('Unknown collector reference')


CollectedInput = models.get_input_model()

class CollectedInputSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    collector = None  # Filled in by viewset at instantiation

    class Meta:
        model = CollectedInput
        fields = '__all__'
        include_write = ('instrument', 'data')

    def __init__(self, *args, **kwargs):
        super(CollectedInputSerializer, self).__init__(*args, **kwargs)
        self.collector = self.context['collector']

    def validate(self, data):
        instrument = data['instrument']

        user = self.context['request'].user
        if isinstance(user, AnonymousUser):
            user = None
        data['user'] = user

        is_unavailable = (not self.collector.is_instrument_allowed(instrument))
        if is_unavailable:
            raise PermissionDenied("[CollectionInstrument=%r] Availability conditions failed. (user=%r, data=%r)" % (
                instrument.pk,
                user,
                data['data'],
            ))

        at_capacity = (not self.collector.is_input_allowed(instrument))
        if at_capacity:
            raise PermissionDenied("[CollectionInstrument=%r] No new inputs allowed. (user=%r, data=%r)" % (
                instrument.pk,
                user,
                data['data'],
            ))

        try:
            data['data'] = self.collector.clean_data(instrument, data['data'])
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

        data = self.collector.validate(instrument, data)

        return data

    # Validation helpers
    def create(self, validated_data):
        return self.collector.store(instance=None, **validated_data)

    def update(self, instance, validated_data):
        return self.collector.store(instance=instance, **validated_data)
