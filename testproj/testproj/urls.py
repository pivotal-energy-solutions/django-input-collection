from django.contrib import admin

from django_input_collection.compat import url, include
from django_input_collection import features


urlpatterns = [
    url(r'^', include('testproj.core.urls')),

    # Temporary
    url(r'^admin/', admin.site.urls),
]


if features.rest_framework:
    urlpatterns.extend([
        url(r'^api/', include('django_input_collection.api.restframework.urls')),
    ])
