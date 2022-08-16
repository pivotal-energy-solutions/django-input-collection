# -*- coding: utf-8 -*-
from collections import defaultdict

from distlib.util import cached_property
from django.forms.models import model_to_dict


class CollectionRequestQueryMinimizerMixin(object):
    def __init__(self, collector):
        self.collector = collector

    @cached_property
    def conditions(self) -> list:
        """Cached list of Conditions"""
        from django_input_collection.models import Condition

        return [
            model_to_dict(x)
            for x in Condition.objects.filter(instrument_id__in=self.instrument_ids)
        ]

    @cached_property
    def condition_group_ids(self) -> list:
        """Cached list of Condition Group IDs"""
        return [x["condition_group"] for x in self.conditions]

    @cached_property
    def condition_groups(self) -> list:
        """Cached list of Condition Groups"""
        from django_input_collection.models import ConditionGroup

        return [
            model_to_dict(x, exclude=["cases", "child_groups"])
            for x in ConditionGroup.objects.filter(id__in=self.condition_group_ids)
        ]

    @cached_property
    def child_condition_groups(self) -> list:
        """Cached list of Child Condition Group IDs

        Note the recursive component of this is not supported one level only.
        """
        from django_input_collection.models import ConditionGroup

        ChildThrough = ConditionGroup.child_groups.through
        children = ChildThrough.objects.filter(from_conditiongroup_id__in=self.condition_group_ids)
        results = []
        for item in children.select_related("to_conditiongroup"):
            data = model_to_dict(item.to_conditiongroup, exclude=["cases", "child_groups"])
            data["from_group"] = item.from_conditiongroup_id
            results.append(data)
        return results

    @cached_property
    def cases(self) -> list:
        """Cached list of Test Cases"""
        from django_input_collection.models import ConditionGroup

        condition_group_ids = self.condition_group_ids
        condition_group_ids += [x["id"] for x in self.child_condition_groups]

        CaseThrough = ConditionGroup.cases.through
        cases = CaseThrough.objects.filter(
            conditiongroup_id__in=condition_group_ids
        ).select_related("case")

        results = []
        for item in cases:
            data = model_to_dict(item.case)
            data["condition_group"] = item.conditiongroup_id
            results.append(data)
        return results

    @cached_property
    def suggested_responses(self) -> list:
        """Cached list of Suggested Responses"""

        from django_input_collection.models import CollectionInstrument

        BoundSuggestedResponseThrough = CollectionInstrument.suggested_responses.through

        suggested_responses = BoundSuggestedResponseThrough.objects.filter(
            collection_instrument_id__in=self.instrument_ids
        ).select_related("suggested_response")
        result = []
        for item in suggested_responses:
            data = model_to_dict(item)
            data["bound_suggested_response_id"] = data.pop("id")
            data["suggested_response_id"] = item.suggested_response_id
            data["suggested_response"] = item.suggested_response.data
            result.append(data)
        return result

    @cached_property
    def instrument_ids(self) -> list:
        """Cached list of instrument IDS"""
        return [x["id"] for x in self.instruments]

    @cached_property
    def instruments(self) -> list:
        """Cached list of instruments"""

        instruments = (
            self.collector.collection_request.collectioninstrument_set.all().select_related(
                "response_policy", "measure", "segment", "group", "type"
            )
        )

        results = []
        for item in instruments:
            data = model_to_dict(item, exclude=["suggested_responses"])
            data["response_policy_info"] = model_to_dict(item.response_policy)
            data["measure"] = f"{item.measure.id}"
            data["segment"] = f"{item.segment.id}" if item.segment else None
            data["group"] = f"{item.group.id}" if item.group else None
            data["type"] = f"{item.type.id}" if item.type else None
            data["_instrument_object"] = item
            results.append(data)
        return results

    @cached_property
    def get_collected_inputs_info(self) -> dict:
        inputs_info = defaultdict(list)

        queryset = self.collector.collection_request.collectedinput_set.filter_for_context(
            **self.collector.context
        )
        for input in queryset:
            inputs_info[input.instrument_id].append(model_to_dict(input))

        return inputs_info

    def get_method_info(self, instrument, suggested_responses=None):
        """
        Resolve a method for the given instrument based on self.measure_methods, or
        self.type_methods, whichever is resolvable first.
        """

        method = self.collector.get_method(instrument)
        method_info = method.serialize(
            instrument=instrument, suggested_responses=suggested_responses
        )
        # print(method_info)
        return method_info


class Specification(CollectionRequestQueryMinimizerMixin):
    __version__ = (0, 0, 0, "dev")

    @property
    def data(self):
        """Returns a JSON-safe spec for another tool to correctly supply inputs."""
        meta_info = self.get_meta()
        identifier = self.collector.get_identifier()
        collection_request_info = model_to_dict(self.collector.collection_request)
        inputs_info = self.get_collected_inputs_info
        instruments_info = self.get_instruments_info()

        info = {
            "meta": meta_info,
            "collector": identifier,
            "collection_request": collection_request_info,
            "segment": self.collector.segment,
            "group": self.collector.group,
            "groups": self.collector.groups,
            "instruments_info": instruments_info,
            "collected_inputs": inputs_info,
        }
        return info

    def get_meta(self):
        return {
            "version": self.collector.__version__,
            "serializer_version": self.__version__,
        }

    def get_condition_group_data(self, condition_dict: dict | None):
        """Correctly format the condition group dataset"""
        if condition_dict is None:
            return

        cases = [x for x in self.cases if x["condition_group"] == condition_dict["id"]]

        child_groups = [
            x for x in self.child_condition_groups if x["from_group"] == condition_dict["id"]
        ]

        return {
            "id": condition_dict["id"],
            "nickname": condition_dict["nickname"],
            "requirement_type": condition_dict["requirement_type"],
            "child_groups": [self.get_condition_group_data(x) for x in child_groups],
            "cases": [
                {
                    "id": x["id"],
                    "nickname": x["nickname"],
                    "match_type": x["match_type"],
                    "match_data": x["match_data"],
                }
                for x in cases
            ],
        }

    def get_condition_data(self, condition_dict):
        """Correctly format the condition dataset"""
        condition_group = next(
            (
                x
                for x in self.child_condition_groups
                if x["id"] == condition_dict["condition_group"]
            ),
            None,
        )

        if condition_group is None:
            condition_group = next(
                (x for x in self.condition_groups if x["id"] == condition_dict["condition_group"]),
                None,
            )

        return {
            "id": condition_dict["id"],
            "instrument": condition_dict["instrument"],
            "condition_group": self.get_condition_group_data(condition_group),
            "data_getter": condition_dict["data_getter"],
        }

    def get_child_conditions_data(self, instrument_dict: dict) -> list | None:
        """Formatted child conditions"""
        # What makes this difficult is I have no idea what the use case for this.
        # What I've pieced together is that on CollectionInstrument there is get_child_conditions
        conditions = [
            x
            for x in self.conditions
            if x["data_getter"]
            in [f'instrument:{instrument_dict["id"]}', f'instrument:{instrument_dict["measure"]}']
        ]

        return [self.get_condition_data(x) for x in conditions]

    def get_instrument_data(self, instrument_dict):
        """Formatted child conditions"""

        suggested_responses = [
            {"id": x["suggested_response_id"], "data": x["suggested_response"]}
            for x in self.suggested_responses
            if x["collection_instrument"] == instrument_dict["id"]
        ]

        conditions = [x for x in self.conditions if x["instrument"] == instrument_dict["id"]]
        instrument = instrument_dict.pop("_instrument_object", None)
        data = {
            "id": instrument_dict["id"],
            "collection_request": self.collector.collection_request.id,
            "measure": instrument_dict["measure"],
            "segment": instrument_dict["segment"],
            "group": instrument_dict.get("group"),
            "type": instrument_dict["type"],
            "order": instrument_dict["order"],
            "text": instrument_dict["text"],
            "description": instrument_dict["description"],
            "help": instrument_dict["help"],
            "response_policy": instrument_dict["response_policy"],
            "test_requirement_type": instrument_dict["test_requirement_type"],
            "response_info": {
                "response_policy": instrument_dict["response_policy_info"],
                "suggested_responses": suggested_responses,
                "method": self.get_method_info(instrument, suggested_responses),
            },
            "collected_inputs": self.get_collected_inputs_info.get(instrument_dict["id"]),
            "conditions": [self.get_condition_data(x) for x in conditions],
            "child_conditions": self.get_child_conditions_data(instrument_dict),
        }
        return data

    def get_instruments_info(self):
        data = {
            "instruments": {
                inst["id"]: inst
                for inst in [self.get_instrument_data(inst) for inst in self.instruments]
            },
            "ordering": [],
        }
        # No idea why this is ordered without conditions but ok.
        for key, item in data["instruments"].items():
            if not item.get("conditions"):
                data["ordering"].append(key)
        return data

    # def legacy_get_instruments_info(self, inputs_info=None):
    #     """DO NOT USE THIS IT IS COMPLETE QUERY HOG!"""
    #     ordering = list(
    #         self.collector.collection_request.collectioninstrument_set.filter(
    #             conditions=None
    #         ).values_list("id", flat=True)
    #     )
    #     instruments_info = {
    #         "instruments": {},
    #         "ordering": ordering,
    #     }
    #
    #     if inputs_info is None:
    #         inputs_info = {}
    #
    #     queryset = self.collector.collection_request.collectioninstrument_set.all()
    #
    #     for instrument in queryset:
    #         info = model_to_dict(instrument, exclude=["suggested_responses"])
    #         info["response_info"] = self.get_instrument_response_info(instrument)
    #         info["collected_inputs"] = inputs_info.get(instrument.pk)
    #         info["conditions"] = [
    #             self.get_condition_info(condition) for condition in instrument.conditions.all()
    #         ]
    #         info["child_conditions"] = [
    #             self.get_condition_info(condition)
    #             for condition in instrument.get_child_conditions()
    #         ]
    #
    #         instruments_info["instruments"][instrument.id] = info
    #
    #     return instruments_info
    #
    # def get_condition_info(self, condition):
    #     condition_info = model_to_dict(condition)
    #
    #     condition_info["condition_group"] = self.get_condition_group_info(condition.condition_group)
    #
    #     return condition_info
    #
    # def get_condition_group_info(self, group):
    #     child_queryset = group.child_groups.prefetch_related("cases")
    #
    #     group_info = model_to_dict(group)
    #     group_info["cases"] = list(map(model_to_dict, group.cases.all()))
    #     group_info["child_groups"] = []
    #     for child_group in child_queryset:
    #         group_info["child_groups"].append(self.get_condition_group_info(child_group))
    #
    #     return group_info

    #
    # def get_instrument_response_info(self, instrument):
    #     """Returns input specifications for data this instruments wants to collect."""
    #     policy_info = model_to_dict(instrument.response_policy)
    #     suggested_responses_info = self.get_suggested_responses_info(instrument)
    #     method_info = self.get_method_info(instrument)
    #
    #     input_info = {
    #         "response_policy": policy_info,
    #         "suggested_responses": suggested_responses_info,
    #         "method": method_info,
    #     }
    #     return input_info
    #
    # def get_suggested_responses_info(self, instrument):
    #     queryset = instrument.suggested_responses.all()
    #     suggested_responses_info = list(map(model_to_dict, queryset))
    #     return suggested_responses_info


class BaseAPISpecification(Specification):
    content_type = "application/json"

    def get_meta(self):
        meta_info = super(BaseAPISpecification, self).get_meta()
        meta_info["api"] = self.get_api_info()
        return meta_info

    def get_api_info(self):
        return {
            "content_type": self.content_type,
            "endpoints": {},
            # Repeated from top-level spec for convenience
            "collector": self.collector.get_identifier(),
            "collection_request": self.collector.collection_request.id,
        }
