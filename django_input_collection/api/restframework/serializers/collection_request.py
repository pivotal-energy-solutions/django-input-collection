# -*- coding: utf-8 -*-
from rest_framework import serializers

from ....models import CollectionRequest
from .utils import ReadWriteToggleMixin


class CollectionRequestSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    class Meta:
        model = CollectionRequest
        fields = "__all__"
