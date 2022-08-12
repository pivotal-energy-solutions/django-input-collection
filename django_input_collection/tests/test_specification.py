# -*- coding: utf-8 -*-
from django.test import TestCase

from . import factories
from ..api.restframework.collection import RestFrameworkCollector


class InstrumentTests(TestCase):
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

    def test_specification(self):

        with self.assertNumQueries(25):
            print(self.collector.specification_json)
