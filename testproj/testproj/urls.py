from django.contrib import admin

from django_input_collection.compat import url, include

urlpatterns = [
    url(r'^', include('testproj.core.urls')),

    # API
    url(r'^api/', include('django_input_collection.api.restframework.urls')),

    # Temporary
    url(r'^admin/', admin.site.urls),
]
