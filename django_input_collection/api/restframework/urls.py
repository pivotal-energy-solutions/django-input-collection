from django.conf import settings

from rest_framework import routers

from ...compat import url
from . import api


router = routers.SimpleRouter()

# Always available
router.register(r'request', api.CollectionRequestViewSet, base_name='request')
router.register(r'measure', api.MeasureViewSet, base_name='measure')

# Requires a collector in the request args
# NOTE: The use of url parameter is tempting, but this is an explicit deference to the simplicity
# in building data for a static url, not both the data and the url.
router.register(r'segment', api.CollectionGroupViewSet, base_name='segment')
router.register(r'group', api.CollectionGroupViewSet, base_name='group')
router.register(r'instrument', api.CollectionInstrumentViewSet, base_name='instrument')
router.register(r'input', api.CollectedInputViewSet, base_name='input')

app_name = 'collection-api'
urlpatterns = router.urls


if settings.DEBUG:
    urlpatterns += [
        url(r'collector', api.CollectorRegistryView.as_view(), name='registry'),
    ]
