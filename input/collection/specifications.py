from collections import defaultdict

from django.forms.models import model_to_dict


class Specification(object):
    __version__ = (0, 0, 0, 'dev')

    def __init__(self, collector):
        self.collector = collector

    @property
    def data(self):
        """ Returns a JSON-safe spec for another tool to correctly supply inputs. """
        meta_info = self.get_meta()
        identifier = self.collector.get_identifier()
        collection_request_info = model_to_dict(self.collector.collection_request)
        inputs_info = self.get_collected_inputs_info()
        instruments_info = self.get_instruments_info(inputs_info)

        info = {
            'meta': meta_info,
            'collector': identifier,
            'collection_request': collection_request_info,
            'group': self.collector.group,
            'instruments_info': instruments_info,
            'collected_inputs': inputs_info,
        }
        return info

    def get_meta(self):
        return {
            'version': self.collector.__version__,
            'serializer_version': self.__version__,
        }

    def get_instruments_info(self, inputs_info=None):
        ordering = list(self.collector.collection_request.collectioninstrument_set \
                                      .filter(conditions=None) \
                                      .values_list('id', flat=True))
        instruments_info = {
            'instruments': {},
            'ordering': ordering,
        }

        if inputs_info is None:
            inputs_info = {}

        queryset = self.collector.collection_request.collectioninstrument_set.all()

        for instrument in queryset:
            info = model_to_dict(instrument, exclude=['suggested_responses'])
            info['response_info'] = self.get_instrument_response_info(instrument)
            info['collected_inputs'] = inputs_info.get(instrument.pk)
            info['conditions'] = [
                self.get_condition_info(condition) for condition in instrument.conditions.all()
            ]
            info['child_conditions'] = [
                self.get_condition_info(condition) for condition in instrument.child_conditions.all()
            ]

            instruments_info['instruments'][instrument.id] = info

        return instruments_info

    def get_condition_info(self, condition):
        condition_info = model_to_dict(condition)

        condition_info['condition_group'] = self.get_condition_group_info(
            condition.condition_group
        )

        return condition_info

    def get_condition_group_info(self, group):
        child_queryset = group.child_groups.prefetch_related('cases')

        group_info = model_to_dict(group)
        group_info['cases'] = list(map(model_to_dict, group.cases.all()))
        group_info['child_groups'] = []
        for child_group in child_queryset:
            group_info['child_groups'].append(
                self.get_condition_group_info(child_group)
            )

        return group_info

    def get_collected_inputs_info(self):
        inputs_info = defaultdict(list)

        queryset = self.collector.collection_request.collectedinput_set(manager='filtered_objects') \
                                                    .filter_for_context(**self.collector.context)
        for input in queryset:
            inputs_info[input.instrument_id].append(model_to_dict(input))

        return inputs_info

    def get_instrument_response_info(self, instrument):
        """ Returns input specifications for data this instruments wants to collect. """
        policy_info = model_to_dict(instrument.response_policy)
        suggested_responses_info = self.get_suggested_responses_info(instrument)
        method_info = self.get_method_info(instrument)

        input_info = {
            'response_policy': policy_info,
            'suggested_responses': suggested_responses_info,
            'method': method_info,
        }
        return input_info

    def get_suggested_responses_info(self, instrument):
        queryset = instrument.suggested_responses.all()
        suggested_responses_info = list(map(model_to_dict, queryset))
        return suggested_responses_info

    def get_method_info(self, instrument):
        """
        Resolve a method for the given instrument based on self.measure_methods, or
        self.type_methods, whichever is resolvable first.
        """

        method = self.collector.get_method(instrument)
        method_info = method.serialize(instrument)
        return method_info


class BaseAPISpecification(Specification):
    content_type = 'application/json'

    def get_meta(self):
        meta_info = super(BaseAPISpecification, self).get_meta()
        meta_info['api'] = self.get_api_info()
        return meta_info

    def get_api_info(self):
        return {
            'collector': self.collector.get_identifier(),  # repeated from top-level spec
            'content_type': self.content_type,
            'endpoints': {},
        }
