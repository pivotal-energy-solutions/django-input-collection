# -*- coding: utf-8 -*-
from django.urls import reverse

from rest_framework.response import Response
from rest_framework import status

from ...collection import BaseAPICollector, BaseAPISpecification
from ... import models
from . import serializers


class RestFrameworkSpecification(BaseAPISpecification):
    content_type = "application/json"

    def get_api_info(self):
        info = super(RestFrameworkSpecification, self).get_api_info()

        input_list = reverse("collection-api:input-list")
        input_detail = reverse("collection-api:input-detail", kwargs={"pk": "__id__"})
        instrument_list = reverse("collection-api:instrument-list")
        instrument_detail = reverse("collection-api:instrument-detail", kwargs={"pk": "__id__"})

        info["endpoints"] = {
            "input": {
                "list": {"url": input_list, "method": "GET"},
                "add": {"url": input_list, "method": "POST"},
                "get": {"url": input_detail, "method": "GET"},
                "delete": {"url": input_detail, "method": "DELETE"},
            },
            "instrument": {
                "list": {"url": instrument_list, "method": "GET"},
                "get": {"url": instrument_detail, "method": "GET"},
            },
        }
        return info


class RestFrameworkCollector(BaseAPICollector):
    specification_class = RestFrameworkSpecification

    model_codenames = {
        models.Measure: "measure",
        models.CollectionRequest: "request",
        models.CollectionGroup: "segment",
        models.CollectionGroup: "group",
        models.CollectionInstrument: "instrument",
        models.get_input_model(): "input",
    }

    # dynamic rest_framework overrides per model (use codename strings)
    serializer_classes = {}
    pagination_classes = {}

    default_serializer_classes = {
        "measure": serializers.MeasureSerializer,
        "request": serializers.CollectionRequestSerializer,
        "segment": serializers.CollectionGroupSerializer,
        "group": serializers.CollectionGroupSerializer,
        "instrument": serializers.CollectionInstrumentSerializer,
        "input": serializers.CollectedInputSerializer,
    }

    def get_pagination_class(self, model):
        """
        Returns a rest_framework pagination class for the model's viewset.  Returning ``None`` will
        be taken directly (disabling pagination), and ``False`` will ensure rest_framework still
        applies whatever default pagination policy is in effect.
        """
        codename = self.model_codenames.get(model, model)
        return self.pagination_classes.get(codename, False)

    def get_serializer_class(self, model):
        """Returns a rest_framework serializer class for the model's viewset."""
        codename = self.model_codenames.get(model, model)
        return self.serializer_classes.get(codename, self.default_serializer_classes[codename])

    def get_destroy_response(self, instrument):
        """Returns a rest_framework Response when an input is deleted from this instrument."""
        return Response(status=status.HTTP_204_NO_CONTENT)

    def validate(self, instrument, data):
        """Raises any validation errors in the serializer's ``data``."""
        return data
