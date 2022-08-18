from django.db.models import QuerySet
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ....collection import CollectionRequestQueryMinimizerMixin
from ....models import CollectionInstrument
from .bound_suggested_response import BoundSuggestedResponseSerializer
from .contextual_collected_input import ContextualCollectedInputsSerializer
from .utils import ReadWriteToggleMixin


class CollectionInstrumentListSerializer(serializers.ListSerializer):
    class Meta:
        model = CollectionInstrument

    def _get_suggested_responses(self, instrument_id):
        """We have self.context.collector_mixin use it"""
        return [
            {
                "id": x["bound_suggested_response_id"],
                "is_considered_failure": x["is_considered_failure"],
                "comment_required": x["comment_required"],
                "document_required": x["document_required"],
                "photo_required": x["photo_required"],
                "suggested_response": x["suggested_response_id"],
                "_suggested_response": x["bound_suggested_response_id"],
                "data": x["suggested_response"],
            }
            for x in self.mixin.get_suggested_response_data(instrument_id)
        ]

    def get_collectedinput_set(self, obj):
        return self.mixin.get_collected_inputs_info[obj.id]

    def _get_instrument_data(self, instrument_dict):
        """We have self.context.collector_mixin use it"""

        # This is ripe for refactor 540 queries for eto-2022
        collector = self.context.get("collector")
        is_condition_met = collector.is_instrument_allowed(instrument_dict["_instrument_object"])

        return {
            "id": instrument_dict["id"],
            "collection_request": instrument_dict["collection_request"],
            "measure": instrument_dict["measure"],
            "segment": instrument_dict["segment"],
            "group": instrument_dict["group"],
            "type": instrument_dict["type"],
            "order": instrument_dict["order"],
            "text": instrument_dict["text"],
            "description": instrument_dict["description"],
            "help": instrument_dict["help"],
            "is_condition_met": is_condition_met,
            "response_policy": {
                "restrict": instrument_dict["response_policy_info"]["restrict"],
                "multiple": instrument_dict["response_policy_info"]["multiple"],
                "required": instrument_dict["response_policy_info"]["required"],
            },
            "parent_instruments": self.mixin.parent_instrument_ids.get(instrument_dict["id"], []),
            "suggested_responses": self._get_suggested_responses(instrument_dict["id"]),
            "collectedinput_set": self.get_collectedinput_set(
                instrument_dict["_instrument_object"]
            ),
        }

    def to_representation(self, data):

        assert isinstance(data, (QuerySet, list)), f"We need a Queryset. We got {type(data)}"

        if not self.context.get("collector"):
            raise ValidationError("We need to have collector context")
        if not self.context.get("collector_mixin"):
            _collector_mixin = CollectionRequestQueryMinimizerMixin(
                collector=self.context.get("collector")
            )
            self.root._context["collector_mixin"] = _collector_mixin

        self.mixin = self.context.get("collector_mixin")
        return [self._get_instrument_data(x) for x in self.context["collector_mixin"].instruments]


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
