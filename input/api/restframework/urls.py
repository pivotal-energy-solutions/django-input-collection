from rest_framework import routers

from . import api


router = routers.SimpleRouter()

router.register(r'measure', api.MeasureViewSet, base_name='measure')
router.register(r'group', api.CollectionGroupViewSet, base_name='group')
router.register(r'collection-request', api.CollectionRequestViewSet, base_name='collection-request')
router.register(r'instrument', api.CollectionInstrumentViewSet, base_name='instrument')
router.register(r'input', api.CollectedInputViewSet, base_name='input')

app_name = 'api'  # FIXME: too generic?  Not interested in having drf in the name, though
urlpatterns = router.urls
