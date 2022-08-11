from rest_framework import serializers

from ....models import CollectionInstrument
from .bound_suggested_response import BoundSuggestedResponseSerializer
from .contextual_collected_input import ContextualCollectedInputsSerializer
from .utils import ReadWriteToggleMixin


class CollectionInstrumentListSerializer(serializers.ListSerializer):
    class Meta:
        model = CollectionInstrument
        fields = [
            "id",
            "collection_request",
            "measure",
            "segment",
            "group",
            "type",
            "order",
            "text",
            "description",
            "help",
        ]

    def to_representation(self, data):
        return [
            {
                "id": item.pk,
                "collection_request": item.collection_request_id,
                "measure": item.measure_id,
                "segment": item.segment_id,
                "group": item.group_id,
                "type": item.type_id,
                "order": item.order,
                "text": item.text,
                "description": item.description,
                "help": item.help,
                "is_condition_met": True,
                "response_policy": {
                    "restrict": item.response_policy.restrict,
                    "multiple": item.response_policy.multiple,
                    "required": item.response_policy.required,
                },
                "parent_instruments": [],
                "suggested_responses": [],
                "collectedinput_set": [],
            }
            for item in data
        ]


class CollectionInstrumentSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    response_policy = serializers.SerializerMethodField()
    suggested_responses = BoundSuggestedResponseSerializer(
        source="bound_suggested_responses", many=True, read_only=True
    )
    collectedinput_set = ContextualCollectedInputsSerializer()
    is_condition_met = serializers.SerializerMethodField()
    parent_instruments = serializers.PrimaryKeyRelatedField(
        source="get_parent_instruments", many=True, read_only=True
    )

    class Meta:
        model = CollectionInstrument
        fields = [
            "id",
            "collection_request",
            "measure",
            "segment",
            "group",
            "type",
            "order",
            "text",
            "description",
            "help",
            "is_condition_met",
            "response_policy",
            "parent_instruments",
            "suggested_responses",
            "collectedinput_set",
        ]
        list_serializer_class = CollectionInstrumentListSerializer

    def get_response_policy(self, instance):
        return instance.response_policy.get_flags()

    def get_is_condition_met(self, instance):
        collector = self.context["collector"]
        return collector.is_instrument_allowed(instance)
