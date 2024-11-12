from rest_framework import serializers

from ....models import CollectionGroup
from .utils import ReadWriteToggleMixin


class CollectionGroupSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = CollectionGroup
        fields = "__all__"
