from django.contrib import admin

from django.urls import re_path, include
from django_input_collection import features


urlpatterns = [
    re_path(r'^', include('testproj.core.urls')),

    # Temporary
    re_path(r'^admin/', admin.site.urls),
]


if features.rest_framework:
    urlpatterns.extend([
        re_path(r'^api/', include('django_input_collection.api.restframework.urls')),
    ])
