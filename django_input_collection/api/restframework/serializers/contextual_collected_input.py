from rest_framework import serializers

from .... import models

BoundCollectedInput = models.get_input_model()


class ContextualCollectedInputsSerializer(serializers.Serializer):
    """Filters the given CollectedInput queryset for the active context."""

    # NOTE: Don't confuse the context sent to the queryset method for the serializer's own attribute
    # with the same name.

    def to_representation(self, queryset):
        collector = self.context["collector"]
        queryset = queryset.filter_for_context(**collector.context)
        serializer_class = collector.get_serializer_class(BoundCollectedInput)
        serializer = serializer_class(queryset, many=True, context=self.context)
        return serializer.data
