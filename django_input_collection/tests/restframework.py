from unittest import SkipTest

from django.contrib.auth import get_user_model
from django.urls import reverse_lazy

from django_input_collection import features
if features.rest_framework:
    from rest_framework.test import APITestCase, URLPatternsTestCase
    from rest_framework import status
else:
    from django.test import TestCase
    class APITestCase(TestCase):
        pass
    class URLPatternsTestCase(object):
        pass

from ..compat import url, include
from ..collection import Collector
from . import factories


User = get_user_model()


class RestFrameworkTestCase(APITestCase, URLPatternsTestCase):
    @classmethod
    def setUpClass(cls):
        if not features.rest_framework:
            raise SkipTest("rest_framework is unavailable")

        cls.urlpatterns = [
            url(r'^api/', include('django_input_collection.api.restframework.urls')),
        ]
        super(RestFrameworkTestCase, cls).setUpClass()


submit_url = reverse_lazy('collection-api:input-list')


class InputSubmissionTests(RestFrameworkTestCase):
    @classmethod
    def setUpClass(cls):
        super(InputSubmissionTests, cls).setUpClass()

        cls.collection_request = factories.CollectionRequestFactory.create(**{
            'max_instrument_inputs_per_user': 1,
            'max_instrument_inputs': 2,
        })
        cls.instrument = factories.CollectionInstrumentFactory.create(**{
            'collection_request': cls.collection_request,
            'response_policy__restrict': False,
            'response_policy__multiple': False,
        })

        cls.collector = Collector(cls.collection_request)

    def submit(self, payload):
        payload = dict({
            'collector': self.collector.get_identifier()
        }, **payload)
        response = self.client.post(submit_url, payload, format='json')
        return response.status_code

    def test_submit(self):
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': 'foo'}), status.HTTP_201_CREATED)

    def test_submit_bad_collector_is_rejected(self):
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': 'foo', 'collector': 'fake'}), status.HTTP_400_BAD_REQUEST)

    def test_submit_bad_instrument_is_rejected(self):
        self.assertEqual(self.submit({'instrument': 0, 'data': 'foo'}), status.HTTP_400_BAD_REQUEST)

    def test_submit_bad_data_is_rejected(self):
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': {'foo': 'bar'}}), status.HTTP_400_BAD_REQUEST)

    def test_submit_planned_multiple_data_without_matching_input_model_is_rejected(self):
        multi_instrument = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
            'response_policy__multiple': True,
        })
        self.assertEqual(self.submit({'instrument': multi_instrument.id, 'data': ['foo', 'bar']}), status.HTTP_400_BAD_REQUEST)

    def test_submit_unexpected_multiple_data_is_rejected(self):
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': ['foo', 'bar']}), status.HTTP_400_BAD_REQUEST)

    def test_submit_policy_restrict_rejects_custom(self):
        restrict_instrument = factories.CollectionInstrumentFactory.create(**{
            'collection_request': self.collection_request,
            'response_policy__nickname': 'no custom',
            'response_policy__restrict': True,
            'suggested_responses': [
                factories.SuggestedResponseFactory.create(data='foo'),
                factories.SuggestedResponseFactory.create(data='bar'),
            ],
        })
        self.assertEqual(self.submit({'instrument': restrict_instrument.id, 'data': 'baz'}), status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.submit({'instrument': restrict_instrument.id, 'data': 'foo'}), status.HTTP_201_CREATED)

    def test_submit_too_many_inputs_for_user_is_rejected(self):
        user = User.objects.create(username='user')
        self.client.force_login(user)
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': 'foo'}), status.HTTP_201_CREATED)
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': 'bar'}), status.HTTP_403_FORBIDDEN)

    def test_submit_too_many_inputs_is_rejected(self):
        user = User.objects.create(username='user1')
        self.client.force_login(user)
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': 'foo'}), status.HTTP_201_CREATED)

        user = User.objects.create(username='user2')
        self.client.force_login(user)
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': 'bar'}), status.HTTP_201_CREATED)

        user = User.objects.create(username='user3')
        self.client.force_login(user)
        self.assertEqual(self.submit({'instrument': self.instrument.id, 'data': 'baz'}), status.HTTP_403_FORBIDDEN)
