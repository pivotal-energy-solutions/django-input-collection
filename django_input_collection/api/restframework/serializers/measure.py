from rest_framework import serializers

from ....models import Measure
from .utils import ReadWriteToggleMixin


class MeasureSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = Measure
        fields = "__all__"
