# -*- coding: utf-8 -*-
from django.contrib import admin

from django.urls import path, include
from django_input_collection import features


urlpatterns = [
    path("", include("testproj.core.urls")),
    # Temporary
    path(r"admin/", admin.site.urls),
]


if features.rest_framework:
    urlpatterns.extend(
        [
            path("api/", include("django_input_collection.api.restframework.urls")),
        ]
    )
