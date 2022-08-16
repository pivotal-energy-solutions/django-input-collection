# -*- coding: utf-8 -*-

from django.test import TestCase

from . import factories
from ..api.restframework.collection import RestFrameworkCollector


class InstrumentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(InstrumentTests, cls).setUpClass()

        cls.collection_request = factories.CollectionRequestFactory.create(
            max_instrument_inputs=2,
            max_instrument_inputs_per_user=1,
        )

        cls.parent_instrument = factories.CollectionInstrumentFactory.create(
            id=10,
            collection_request=cls.collection_request,
            group=factories.CollectionGroupFactory(id="Foo"),
            segment=factories.CollectionGroupFactory(id="Segment"),
            type=factories.CollectionInstrumentTypeFactory(id="data_type"),
            suggested_responses=[
                factories.SuggestedResponseFactory.create(data="Yes"),
                factories.SuggestedResponseFactory.create(data="No"),
            ],
        )

        factories.CollectedInputFactory.create(
            collection_request=cls.collection_request,
            instrument=cls.parent_instrument,
            data={"input": "foo"},
        )

        cls.condition = factories.ConditionFactory.create(
            data_getter=f"instrument:{cls.parent_instrument.measure}",
            instrument=factories.CollectionInstrumentFactory.create(
                id=11,
                collection_request=cls.collection_request,
            ),
            condition_group=factories.ConditionGroupFactory.create(
                requirement_type="all-pass",
                cases=[
                    factories.CaseFactory.create(match_type="all-custom"),
                    factories.CaseFactory.create(match_type="all-custom"),
                ],
            ),
        )
        cls.instrument = cls.condition.instrument
        factories.CollectedInputFactory.create(
            collection_request=cls.collection_request,
            instrument=cls.instrument,
            data={"input": "bar"},
        )
        factories.CollectedInputFactory.create(
            collection_request=cls.collection_request,
            instrument=cls.instrument,
            data={"input": "baz"},
        )

        cls.condition_2 = factories.ConditionFactory.create(
            id=999,
            data_getter=f"instrument:{cls.instrument.id}",
            instrument=factories.CollectionInstrumentFactory.create(
                id=899,
                collection_request=cls.collection_request,
            ),
            condition_group=factories.ConditionGroupFactory.create(
                id=799,
                requirement_type="one-pass",
                cases=[
                    factories.CaseFactory.create(id=699, match_type="all-custom"),
                ],
                child_groups=[
                    factories.ConditionGroupFactory.create(
                        id=599,
                        nickname="child1",
                        requirement_type="all-pass",
                        cases=[
                            factories.CaseFactory.create(id=499, match_type="exact"),
                            factories.CaseFactory.create(id=399, match_type="all-custom"),
                        ],
                    ),
                ],
            ),
        )

        cls.instrument_3 = cls.condition_2.instrument

        cls.condition_3 = factories.ConditionFactory.create(
            id=1999,
            data_getter=f"instrument:{cls.instrument.id}",
            instrument=cls.instrument_3,
            condition_group=factories.ConditionGroupFactory.create(
                id=1799,
                requirement_type="one-pass",
                cases=[
                    factories.CaseFactory.create(id=1699, match_type="all-custom"),
                ],
                child_groups=[],
            ),
        )

        cls.collector = RestFrameworkCollector(cls.collection_request)

    def test_specification_final_query_count(self):

        self.collector = RestFrameworkCollector(self.collection_request)
        specification = self.collector.get_specification()

        with self.assertNumQueries(7):
            specification.data

    def test_specification_query_counts(self):

        self.collector = RestFrameworkCollector(self.collection_request)
        specification = self.collector.get_specification()

        with self.assertNumQueries(1):
            instruments = specification.instruments
        self.assertEqual(len(instruments), 3)
        # print(f"{len(instruments)} {instruments=}")

        with self.assertNumQueries(1):
            collected_inputs = specification.get_collected_inputs_info
        # print(f"{len(collected_inputs)} {collected_inputs=}")

        with self.assertNumQueries(1):
            suggested_responses = specification.suggested_responses
        # print(f"{len(suggested_responses)} {suggested_responses=}")

        with self.assertNumQueries(1):
            conditions = specification.conditions
        self.assertEqual(len(conditions), 3)
        # print(f"{len(conditions)} {conditions=}")

        with self.assertNumQueries(1):
            condition_groups = specification.condition_groups
        self.assertEqual(len(condition_groups), 3)
        # print(f"{len(condition_groups)} {condition_groups=}")

        with self.assertNumQueries(1):
            child_condition_groups = specification.child_condition_groups
        self.assertEqual(len(child_condition_groups), 1)
        # print(f"{len(child_condition_groups)} {child_condition_groups=}")

        with self.assertNumQueries(1):
            cases = specification.cases
        self.assertEqual(len(cases), 6)
        # print(f"{len(cases)} {cases=}")

        with self.assertNumQueries(45):
            self.collector = RestFrameworkCollector(self.collection_request)
            specification = self.collector.get_specification()
            default = specification.legacy_get_instruments_info()

        with self.assertNumQueries(7):
            self.collector = RestFrameworkCollector(self.collection_request)
            specification = self.collector.get_specification()
            data = specification.get_instruments_info()

        # from django_input_collection.models import ConditionGroup
        # from django.forms import model_to_dict
        #
        # for instrument in CollectionInstrument.objects.all():
        #     inst_data = model_to_dict(instrument)
        #     print(f"Instrument {inst_data}")
        #     for cond in Condition.objects.filter(instrument=inst_data["id"]):
        #         cond_data = model_to_dict(cond)
        #         print(f" - Condition {cond_data}")
        #         for cg in ConditionGroup.objects.filter(id=cond_data["condition_group"]):
        #             cg_data = model_to_dict(cg)
        #             print(f"  - Condition Group {cg_data}")
        #             for case in cg_data["cases"]:
        #                 print(f"    - Case {model_to_dict(case)}")
        #             for child in cg_data["child_groups"]:
        #                 c_data = model_to_dict(child)
        #                 print(f"    - Child - {c_data}")
        #                 for case in c_data["cases"]:
        #                     print(f"      - Case {model_to_dict(case)}")

        # with open("default.json", "w") as fp:
        #     fp.write(f"{json.dumps(default, indent=4)}\n")
        #
        # with open("new.json", "w") as fp:
        #     fp.write(f"{json.dumps(data, indent=4)}\n")
        #
        # def build_assertions(value, key="data"):
        #
        #     if isinstance(value, dict):
        #         for k, v in value.items():
        #             build_assertions(v, f"{key}[{k!r}]")
        #     elif isinstance(value, list):
        #         for idx, v in enumerate(value):
        #             build_assertions(v, f"{key}[{idx}]")
        #     else:
        #         print(f"self.assertEqual({key}, {value!r})")

        # build_assertions(data)

        self.assertEqual(data["instruments"][11]["id"], 11)
        self.assertEqual(data["instruments"][11]["collection_request"], 1)
        self.assertEqual(data["instruments"][11]["measure"], "measure-1")
        self.assertEqual(data["instruments"][11]["segment"], None)
        self.assertEqual(data["instruments"][11]["group"], "default")
        self.assertEqual(data["instruments"][11]["type"], None)
        self.assertEqual(data["instruments"][11]["order"], 1)
        self.assertEqual(data["instruments"][11]["text"], "text 1")
        self.assertEqual(data["instruments"][11]["description"], "description 1")
        self.assertEqual(data["instruments"][11]["help"], "help 1")
        self.assertEqual(data["instruments"][11]["response_policy"], 1)
        self.assertEqual(data["instruments"][11]["test_requirement_type"], "all-pass")
        self.assertEqual(data["instruments"][11]["response_info"]["response_policy"]["id"], 1)
        self.assertEqual(
            data["instruments"][11]["response_info"]["response_policy"]["nickname"], "default"
        )
        self.assertEqual(
            data["instruments"][11]["response_info"]["response_policy"]["is_singleton"], False
        )
        self.assertEqual(
            data["instruments"][11]["response_info"]["response_policy"]["restrict"], False
        )
        self.assertEqual(
            data["instruments"][11]["response_info"]["response_policy"]["multiple"], False
        )
        self.assertEqual(
            data["instruments"][11]["response_info"]["response_policy"]["required"], False
        )
        self.assertEqual(
            data["instruments"][11]["response_info"]["method"]["meta"]["method_class"],
            "django_input_collection.collection.methods.base.InputMethod",
        )
        self.assertEqual(
            data["instruments"][11]["response_info"]["method"]["meta"]["data_type"], None
        )
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["id"], 2)
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["collection_request"], 1)
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["instrument"], 11)
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["user"], None)
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["version"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["collector_class"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["collector_id"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["collector_version"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["collector_comment"], None)
        self.assertEqual(data["instruments"][11]["collected_inputs"][0]["data"], "{'input': 'bar'}")
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["id"], 3)
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["collection_request"], 1)
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["instrument"], 11)
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["user"], None)
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["version"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["collector_class"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["collector_id"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["collector_version"], "")
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["collector_comment"], None)
        self.assertEqual(data["instruments"][11]["collected_inputs"][1]["data"], "{'input': 'baz'}")
        self.assertEqual(data["instruments"][11]["conditions"][0]["id"], 1)
        self.assertEqual(data["instruments"][11]["conditions"][0]["instrument"], 11)
        self.assertEqual(data["instruments"][11]["conditions"][0]["condition_group"]["id"], 1)
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["nickname"], "Group 0"
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["requirement_type"],
            "all-pass",
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][0]["id"], 1
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][0]["nickname"],
            "Case 0",
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][0]["match_type"],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][0]["match_data"],
            "",
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][1]["id"], 2
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][1]["nickname"],
            "Case 1",
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][1]["match_type"],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["condition_group"]["cases"][1]["match_data"],
            "",
        )
        self.assertEqual(
            data["instruments"][11]["conditions"][0]["data_getter"], "instrument:measure-0"
        )
        self.assertEqual(data["instruments"][11]["child_conditions"][0]["id"], 999)
        self.assertEqual(data["instruments"][11]["child_conditions"][0]["instrument"], 899)
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["id"], 799
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["nickname"], "Group 2"
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["requirement_type"],
            "one-pass",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "id"
            ],
            599,
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "nickname"
            ],
            "child1",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "requirement_type"
            ],
            "all-pass",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["id"],
            399,
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["nickname"],
            "Case 4",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["match_type"],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["match_data"],
            "",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["id"],
            499,
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["nickname"],
            "Case 3",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["match_type"],
            "exact",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["match_data"],
            "",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["cases"][0]["id"], 699
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["cases"][0][
                "nickname"
            ],
            "Case 2",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["cases"][0][
                "match_type"
            ],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["condition_group"]["cases"][0][
                "match_data"
            ],
            "",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][0]["data_getter"], "instrument:11"
        )
        self.assertEqual(data["instruments"][11]["child_conditions"][1]["id"], 1999)
        self.assertEqual(data["instruments"][11]["child_conditions"][1]["instrument"], 899)
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["condition_group"]["id"], 1799
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["condition_group"]["nickname"], "Group 3"
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["condition_group"]["requirement_type"],
            "one-pass",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["condition_group"]["cases"][0]["id"],
            1699,
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["condition_group"]["cases"][0][
                "nickname"
            ],
            "Case 5",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["condition_group"]["cases"][0][
                "match_type"
            ],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["condition_group"]["cases"][0][
                "match_data"
            ],
            "",
        )
        self.assertEqual(
            data["instruments"][11]["child_conditions"][1]["data_getter"], "instrument:11"
        )
        self.assertEqual(data["instruments"][899]["id"], 899)
        self.assertEqual(data["instruments"][899]["collection_request"], 1)
        self.assertEqual(data["instruments"][899]["measure"], "measure-2")
        self.assertEqual(data["instruments"][899]["segment"], None)
        self.assertEqual(data["instruments"][899]["group"], "default")
        self.assertEqual(data["instruments"][899]["type"], None)
        self.assertEqual(data["instruments"][899]["order"], 2)
        self.assertEqual(data["instruments"][899]["text"], "text 2")
        self.assertEqual(data["instruments"][899]["description"], "description 2")
        self.assertEqual(data["instruments"][899]["help"], "help 2")
        self.assertEqual(data["instruments"][899]["response_policy"], 1)
        self.assertEqual(data["instruments"][899]["test_requirement_type"], "all-pass")
        self.assertEqual(data["instruments"][899]["response_info"]["response_policy"]["id"], 1)
        self.assertEqual(
            data["instruments"][899]["response_info"]["response_policy"]["nickname"], "default"
        )
        self.assertEqual(
            data["instruments"][899]["response_info"]["response_policy"]["is_singleton"], False
        )
        self.assertEqual(
            data["instruments"][899]["response_info"]["response_policy"]["restrict"], False
        )
        self.assertEqual(
            data["instruments"][899]["response_info"]["response_policy"]["multiple"], False
        )
        self.assertEqual(
            data["instruments"][899]["response_info"]["response_policy"]["required"], False
        )
        self.assertEqual(
            data["instruments"][899]["response_info"]["method"]["meta"]["method_class"],
            "django_input_collection.collection.methods.base.InputMethod",
        )
        self.assertEqual(
            data["instruments"][899]["response_info"]["method"]["meta"]["data_type"], None
        )
        self.assertEqual(data["instruments"][899]["collected_inputs"], None)
        self.assertEqual(data["instruments"][899]["conditions"][0]["id"], 999)
        self.assertEqual(data["instruments"][899]["conditions"][0]["instrument"], 899)
        self.assertEqual(data["instruments"][899]["conditions"][0]["condition_group"]["id"], 799)
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["nickname"], "Group 2"
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["requirement_type"],
            "one-pass",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0]["id"],
            599,
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "nickname"
            ],
            "child1",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "requirement_type"
            ],
            "all-pass",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["id"],
            399,
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["nickname"],
            "Case 4",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["match_type"],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][0]["match_data"],
            "",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["id"],
            499,
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["nickname"],
            "Case 3",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["match_type"],
            "exact",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["child_groups"][0][
                "cases"
            ][1]["match_data"],
            "",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["cases"][0]["id"], 699
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["cases"][0]["nickname"],
            "Case 2",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["cases"][0]["match_type"],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][0]["condition_group"]["cases"][0]["match_data"],
            "",
        )
        self.assertEqual(data["instruments"][899]["conditions"][0]["data_getter"], "instrument:11")
        self.assertEqual(data["instruments"][899]["conditions"][1]["id"], 1999)
        self.assertEqual(data["instruments"][899]["conditions"][1]["instrument"], 899)
        self.assertEqual(data["instruments"][899]["conditions"][1]["condition_group"]["id"], 1799)
        self.assertEqual(
            data["instruments"][899]["conditions"][1]["condition_group"]["nickname"], "Group 3"
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][1]["condition_group"]["requirement_type"],
            "one-pass",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][1]["condition_group"]["cases"][0]["id"], 1699
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][1]["condition_group"]["cases"][0]["nickname"],
            "Case 5",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][1]["condition_group"]["cases"][0]["match_type"],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][899]["conditions"][1]["condition_group"]["cases"][0]["match_data"],
            "",
        )
        self.assertEqual(data["instruments"][899]["conditions"][1]["data_getter"], "instrument:11")
        self.assertEqual(data["instruments"][10]["id"], 10)
        self.assertEqual(data["instruments"][10]["collection_request"], 1)
        self.assertEqual(data["instruments"][10]["measure"], "measure-0")
        self.assertEqual(data["instruments"][10]["segment"], "Segment")
        self.assertEqual(data["instruments"][10]["group"], "Foo")
        self.assertEqual(data["instruments"][10]["type"], "data_type")
        self.assertEqual(data["instruments"][10]["order"], 0)
        self.assertEqual(data["instruments"][10]["text"], "text 0")
        self.assertEqual(data["instruments"][10]["description"], "description 0")
        self.assertEqual(data["instruments"][10]["help"], "help 0")
        self.assertEqual(data["instruments"][10]["response_policy"], 1)
        self.assertEqual(data["instruments"][10]["test_requirement_type"], "all-pass")
        self.assertEqual(data["instruments"][10]["response_info"]["response_policy"]["id"], 1)
        self.assertEqual(
            data["instruments"][10]["response_info"]["response_policy"]["nickname"], "default"
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["response_policy"]["is_singleton"], False
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["response_policy"]["restrict"], False
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["response_policy"]["multiple"], False
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["response_policy"]["required"], False
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["suggested_responses"][0]["id"], 1
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["suggested_responses"][0]["data"], "Yes"
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["suggested_responses"][1]["id"], 2
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["suggested_responses"][1]["data"], "No"
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["method"]["meta"]["method_class"],
            "django_input_collection.collection.methods.base.InputMethod",
        )
        self.assertEqual(
            data["instruments"][10]["response_info"]["method"]["meta"]["data_type"], None
        )
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["id"], 1)
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["collection_request"], 1)
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["instrument"], 10)
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["user"], None)
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["version"], "")
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["collector_class"], "")
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["collector_id"], "")
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["collector_version"], "")
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["collector_comment"], None)
        self.assertEqual(data["instruments"][10]["collected_inputs"][0]["data"], "{'input': 'foo'}")
        self.assertEqual(data["instruments"][10]["child_conditions"][0]["id"], 1)
        self.assertEqual(data["instruments"][10]["child_conditions"][0]["instrument"], 11)
        self.assertEqual(data["instruments"][10]["child_conditions"][0]["condition_group"]["id"], 1)
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["nickname"], "Group 0"
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["requirement_type"],
            "all-pass",
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][0]["id"], 1
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][0][
                "nickname"
            ],
            "Case 0",
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][0][
                "match_type"
            ],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][0][
                "match_data"
            ],
            "",
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][1]["id"], 2
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][1][
                "nickname"
            ],
            "Case 1",
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][1][
                "match_type"
            ],
            "all-custom",
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["condition_group"]["cases"][1][
                "match_data"
            ],
            "",
        )
        self.assertEqual(
            data["instruments"][10]["child_conditions"][0]["data_getter"], "instrument:measure-0"
        )
        self.assertEqual(data["ordering"][0], 10)
