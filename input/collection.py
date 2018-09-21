from collections import defaultdict

from django.forms.models import model_to_dict

from . import models

__all__ = ['Collector', 'store']


def store(instrument, data, instance=None, **model_kwargs):
    """
    Creates a new CollectedInput instance for the given data.  Any additional kwargs are sent to
    the manager's ``create()`` method, in case the CollectedInput model has been swapped and
    requires additional fields to successfully save.
    """
    CollectedInput = models.get_input_model()

    db_data = CollectedInput().serialize_data(data)  # FIXME: classmethod/staticmethod?

    kwargs = {
        'instrument': instrument,
        'data': db_data,

        # Disallow data integrity funnybusiness
        'collection_request': instrument.collection_request,
    }
    kwargs.update(model_kwargs)

    pk = None
    if instance is not None:
        pk = instance.pk
    instance, created = CollectedInput.objects.update_or_create(pk=pk, defaults=kwargs)

    return instance


def get_data_for_suggested_responses(instrument, *responses):
    class missing:
        pass

    values = []

    lookups = dict(instrument.suggested_responses.values_list('id', 'data'))
    for response in responses:
        data = response  # Assume raw passthrough by default

        # Transform data referring to a SuggestedResponse id
        if isinstance(data, dict):
            suggested_response_id = data.get('_suggested_response', missing)
            if suggested_response_id is not missing:
                try:
                    suggested_response_id = int(suggested_response_id)
                except ValueError as e:
                    pass  # It's going to raise again shortly anyway with a better message

                # Verify the coded SuggestedResponse id is valid for this instrument
                data = lookups.get(suggested_response_id, missing)
                if data is missing:
                    raise ValueError("[CollectionInstrument id=%r] Invalid SuggestedResponse id=%r in choices: %r" % (
                        instrument.id,
                        suggested_response_id,
                        lookups,
                    ))

        values.append(data)

    return values


class Collector(object):
    __version__ = (0, 0, 0, 'dev')
    group = 'default'

    def __init__(self, collection_request, group='default', **context):
        self.collection_request = collection_request
        self.context = context
        self.group = group

    @property
    def info(self):
        """ Returns a JSON-safe spec for another tool to correctly supply inputs. """
        meta_info = self.get_meta()
        collection_request_info = model_to_dict(self.collection_request)
        inputs_info = self.get_collected_inputs_info()
        instruments_info = self.get_instruments_info(inputs_info)

        info = {
            'meta': meta_info,
            'collection_request': collection_request_info,
            'group': self.group,
            'instruments_info': instruments_info,
            'collected_inputs': inputs_info,
        }
        return info

    def get_meta(self):
        return {
            'version': self.__version__,
        }

    def get_instruments_info(self, inputs_info=None):
        ordering = list(self.collection_request.collectioninstrument_set.filter(conditions=None) \
                                               .values_list('id', flat=True))
        instruments_info = {
            'instruments': {},
            'ordering': ordering,
        }

        if inputs_info is None:
            inputs_info = {}

        queryset = self.collection_request.collectioninstrument_set.all()

        for instrument in queryset:
            info = model_to_dict(instrument, exclude=['suggested_responses'])
            info['response_info'] = self.get_instrument_input_info(instrument)
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

        queryset = self.collection_request.collectedinput_set(manager='filtered_objects') \
                                          .filter_for_context(**self.context)
        for input in queryset:
            inputs_info[input.instrument_id].append(model_to_dict(input))

        return inputs_info

    def get_instrument_input_info(self, instrument):
        """ Returns input specifications for data this instruments wants to collect. """
        policy_info = model_to_dict(instrument.response_policy)
        suggested_responses_info = self.get_suggested_responses_info(instrument)

        input_info = {
            'response_policy': policy_info,
            'suggested_responses': suggested_responses_info,
        }
        return input_info

    def get_suggested_responses_info(self, instrument):
        queryset = instrument.suggested_responses.all()
        suggested_responses_info = list(map(model_to_dict, queryset))
        return suggested_responses_info


class BaseAPICollector(Collector):
    content_type = 'application/json'

    def get_meta(self):
        meta_info = super(BaseAPICollector, self).get_meta()
        meta_info['api'] = self.get_api_info()
        return meta_info

    def get_api_info(self):
        return {
            'content_type': self.content_type,
            'endpoints': {},
        }
