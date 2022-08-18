from rest_framework import serializers
from .... import models

BoundSuggestedResponse = models.get_boundsuggestedresponse_model()


class BoundSuggestedResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoundSuggestedResponse
        exclude = ["date_created", "date_modified", "collection_instrument"]

    def to_representation(self, obj):
        data = super(BoundSuggestedResponseSerializer, self).to_representation(obj)

        data["_suggested_response"] = obj.id
        data["data"] = obj.suggested_response.data
        return data
