from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('', include('testproj.core.urls')),

    # API
    path('api/', include('django_input_collection.api.restframework.urls')),

    # Temporary
    path('admin/', admin.site.urls),
]
