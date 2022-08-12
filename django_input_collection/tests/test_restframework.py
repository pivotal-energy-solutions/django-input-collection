# -*- coding: utf-8 -*-
import json
from unittest import SkipTest

from django.contrib.auth import get_user_model
from django.urls import path, reverse_lazy, include

from django_input_collection import features

if features.rest_framework:
    from rest_framework.test import APITestCase, URLPatternsTestCase
    from rest_framework import status
    from django_input_collection.api.restframework.collection import RestFrameworkCollector
else:
    from django.test import TestCase

    class APITestCase(TestCase):
        pass

    class URLPatternsTestCase(object):
        pass


from . import factories


User = get_user_model()


class RestFrameworkTestCase(APITestCase, URLPatternsTestCase):
    @classmethod
    def setUpClass(cls):
        if not features.rest_framework:
            raise SkipTest("rest_framework is unavailable")

        cls.urlpatterns = [
            path("api/", include("django_input_collection.api.restframework.urls")),
        ]
        super(RestFrameworkTestCase, cls).setUpClass()


submit_url = reverse_lazy("collection-api:input-list")


class InputSubmissionTests(RestFrameworkTestCase):
    @classmethod
    def setUpClass(cls):
        super(InputSubmissionTests, cls).setUpClass()

        cls.collection_request = factories.CollectionRequestFactory.create(
            **{
                "max_instrument_inputs_per_user": 1,
                "max_instrument_inputs": 2,
            }
        )
        cls.instrument = factories.CollectionInstrumentFactory.create(
            **{
                "collection_request": cls.collection_request,
                "response_policy__restrict": False,
                "response_policy__multiple": False,
            }
        )

        cls.collector = RestFrameworkCollector(cls.collection_request)

    def submit(self, payload):
        payload = dict({"collector": self.collector.get_identifier()}, **payload)
        response = self.client.post(submit_url, payload, format="json")
        return response.status_code

    def test_submit(self):
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": "foo"}), status.HTTP_201_CREATED
        )

    def test_submit_bad_collector_is_rejected(self):
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": "foo", "collector": "fake"}),
            status.HTTP_403_FORBIDDEN,
        )

    def test_submit_bad_instrument_is_rejected(self):
        self.assertEqual(self.submit({"instrument": 0, "data": "foo"}), status.HTTP_400_BAD_REQUEST)

    def test_submit_bad_data_is_rejected(self):
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": {"foo": "bar"}}),
            status.HTTP_400_BAD_REQUEST,
        )

    def test_submit_planned_multiple_data_without_matching_input_model_is_rejected(self):
        multi_instrument = factories.CollectionInstrumentFactory.create(
            **{
                "collection_request": self.collection_request,
                "response_policy__multiple": True,
            }
        )
        self.assertEqual(
            self.submit({"instrument": multi_instrument.id, "data": ["foo", "bar"]}),
            status.HTTP_400_BAD_REQUEST,
        )

    def test_submit_unexpected_multiple_data_is_rejected(self):
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": ["foo", "bar"]}),
            status.HTTP_400_BAD_REQUEST,
        )

    def test_submit_policy_restrict_rejects_custom(self):
        restrict_instrument = factories.CollectionInstrumentFactory.create(
            **{
                "collection_request": self.collection_request,
                "response_policy__nickname": "no custom",
                "response_policy__restrict": True,
            }
        )

        def bind(instrument, data, **fields):
            suggested_response = factories.SuggestedResponseFactory.create(data=data)
            fields["suggested_response"] = suggested_response
            fields["collection_instrument"] = instrument
            factories.BoundSuggestedResponseFactory.create(**fields)

        bind(restrict_instrument, "foo")
        bind(restrict_instrument, "bar")

        self.assertEqual(
            self.submit({"instrument": restrict_instrument.id, "data": "baz"}),
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.submit({"instrument": restrict_instrument.id, "data": "foo"}),
            status.HTTP_201_CREATED,
        )

    def test_submit_too_many_inputs_for_user_is_rejected(self):
        user = User.objects.create(username="user")
        self.client.force_login(user)
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": "foo"}), status.HTTP_201_CREATED
        )
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": "bar"}),
            status.HTTP_400_BAD_REQUEST,
        )

    def test_submit_too_many_inputs_is_rejected(self):
        user = User.objects.create(username="user1")
        self.client.force_login(user)
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": "foo"}), status.HTTP_201_CREATED
        )

        user = User.objects.create(username="user2")
        self.client.force_login(user)
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": "bar"}), status.HTTP_201_CREATED
        )

        user = User.objects.create(username="user3")
        self.client.force_login(user)
        self.assertEqual(
            self.submit({"instrument": self.instrument.id, "data": "baz"}),
            status.HTTP_400_BAD_REQUEST,
        )


instrument_list = reverse_lazy("collection-api:instrument-list")


class InstrumentTests(RestFrameworkTestCase):
    @classmethod
    def setUpClass(cls):
        super(InstrumentTests, cls).setUpClass()

        cls.collection_request = factories.CollectionRequestFactory.create(
            **{
                "max_instrument_inputs_per_user": 1,
                "max_instrument_inputs": 2,
            }
        )

        cls.parent_instrument = factories.CollectionInstrumentFactory.create(
            **{
                "id": 1,
                "collection_request": cls.collection_request,
            }
        )
        cls.condition = factories.ConditionFactory.create(
            **{
                "data_getter": "instrument:%d" % (cls.parent_instrument.id,),
                "instrument": factories.CollectionInstrumentFactory.create(
                    **{
                        "id": 2,
                        "collection_request": cls.collection_request,
                    }
                ),
                "condition_group": factories.ConditionGroupFactory.create(
                    **{
                        "requirement_type": "all-pass",
                        "cases": [
                            factories.CaseFactory.create(match_type="all-custom"),
                        ],
                    }
                ),
            }
        )
        cls.instrument = cls.condition.instrument

        cls.instrument_3 = factories.CollectionInstrumentFactory.create(
            **{
                "collection_request": cls.collection_request,
                "response_policy__restrict": True,
                "response_policy__multiple": True,
            }
        )

        cls.collector = RestFrameworkCollector(cls.collection_request)

    def test_instrument_pk(self):
        user = User.objects.create(username="user1")
        self.client.force_login(user)

        response = self.client.get(
            reverse_lazy("collection-api:instrument-detail", kwargs={"pk": self.instrument.pk}),
            {
                "collector": self.collector.get_identifier(),
                "request": self.collection_request.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        # print(json.dumps(response.json(), indent=4))

    def test_list_instrument_query_counts(self):
        """Verify that for list serializer we have predictable ta"""
        user = User.objects.create(username="user1")
        self.client.force_login(user)

        # Query 1 - Session
        # Query 2 - User
        # Query 3/4 - Collection Request
        overhead_queries = 4

        # This absolutely needs rework.
        EXPECTED = 21  # WTF

        with self.assertNumQueries(overhead_queries + EXPECTED):
            response = self.client.get(
                instrument_list,
                {
                    "collector": self.collector.get_identifier(),
                    "request": self.collection_request.pk,
                },
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.json()), list)
        self.assertEqual(len(response.json()), 2)

        # print(json.dumps(response.json(), indent=4))

    def test_data_equality(self):
        """Verify that the data we get from a list serializer matches the detail serializer"""

        user = User.objects.create(username="user1")
        self.client.force_login(user)

        response = self.client.get(
            instrument_list,
            {"collector": self.collector.get_identifier(), "request": self.collection_request.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        for item in response.json():
            with self.subTest(f"{item['measure']} equality test"):
                response = self.client.get(
                    reverse_lazy("collection-api:instrument-detail", kwargs={"pk": item["id"]}),
                    {
                        "collector": self.collector.get_identifier(),
                        "request": self.collection_request.pk,
                    },
                    format="json",
                )
                self.assertEqual(set(response.json().keys()), set(item.keys()))
                for key, value in response.json().items():
                    with self.subTest(f"{item['measure']} {key} => {value} == {item[key]}"):
                        self.assertEqual(value, item.get(key))
