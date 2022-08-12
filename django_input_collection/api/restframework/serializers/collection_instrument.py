from rest_framework import serializers

from ....models import CollectionInstrument
from .bound_suggested_response import BoundSuggestedResponseSerializer
from .contextual_collected_input import ContextualCollectedInputsSerializer
from .utils import ReadWriteToggleMixin


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

    def get_response_policy(self, instance):
        return instance.response_policy.get_flags()

    def get_is_condition_met(self, instance):
        collector = self.context["collector"]
        return collector.is_instrument_allowed(instance)
