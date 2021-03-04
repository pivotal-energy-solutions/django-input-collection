from django.conf import settings
from django.urls import path

from rest_framework import routers

from . import api


router = routers.SimpleRouter()

# Always available
router.register(r'request', api.CollectionRequestViewSet, basename='request')
router.register(r'measure', api.MeasureViewSet, basename='measure')

# Requires a collector in the request args
# NOTE: The use of url parameter is tempting, but this is an explicit deference to the simplicity
# in building data for a static url, not both the data and the url.
router.register(r'segment', api.CollectionGroupViewSet, basename='segment')
router.register(r'group', api.CollectionGroupViewSet, basename='group')
router.register(r'instrument', api.CollectionInstrumentViewSet, basename='instrument')
router.register(r'input', api.CollectedInputViewSet, basename='input')

app_name = 'collection-api'
urlpatterns = router.urls


if settings.DEBUG:
    urlpatterns += [
        path('collector', api.CollectorRegistryView.as_view(), name='registry'),
    ]
