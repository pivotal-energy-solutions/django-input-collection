from rest_framework import routers

from input.api.restframework import api


router = routers.SimpleRouter()
router.register(r'measure', api.MeasureViewSet, base_name='measure')
router.register(r'group', api.CollectionGroupViewSet, base_name='group')
router.register(r'collection-request', api.CollectionRequestViewSet, base_name='collection-request')
router.register(r'instrument', api.CollectionInstrumentViewSet, base_name='instrument')
router.register(r'input', api.CollectionInputViewSet, base_name='input')
