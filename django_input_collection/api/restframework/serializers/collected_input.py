# -*- coding: utf-8 -*-
from django.contrib.auth.models import AnonymousUser
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .... import models
from .utils import ReadWriteToggleMixin

CollectedInput = models.get_input_model()


class CollectedInputSerializer(ReadWriteToggleMixin, serializers.ModelSerializer):
    collector = None  # Filled in by viewset at instantiation

    class Meta:
        model = CollectedInput
        fields = "__all__"
        include_write = ("instrument", "data")

    def __init__(self, *args, **kwargs):
        super(CollectedInputSerializer, self).__init__(*args, **kwargs)
        self.collector = self.context["collector"]

    def validate(self, data):
        user = self.context["request"].user
        if isinstance(user, AnonymousUser):
            user = None
        data["user"] = user

        try:
            data = self.collector.clean_payload(data)
        except ValidationError as e:
            self.collector.raise_error(e)
        return data

    # Validation helpers
    def create(self, validated_data):
        return self.collector.store(instance=None, **validated_data)

    def update(self, instance, validated_data):
        return self.collector.store(instance=instance, **validated_data)
