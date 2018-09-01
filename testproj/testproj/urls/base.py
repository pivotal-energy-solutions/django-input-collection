from django.contrib import admin
from django.urls import path, include

from . import api


urlpatterns = [
    path('', include('testproj.core.urls')),

    # API
    path('api/', include(api.router.urls)),

    # Temporary
    path('admin/', admin.site.urls),
]
