import re
from django.apps import apps as django_apps
from collections.abc import Iterable

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models.query import Q
from django.utils.encoding import force_str


def get_input_model():
    try:
        return django_apps.get_model(settings.INPUT_COLLECTEDINPUT_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "INPUT_COLLECTEDINPUT_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "INPUT_COLLECTEDINPUT_MODEL refers to model '%s' that has not been installed"
            % settings.INPUT_COLLECTEDINPUT_MODEL
        )


def get_boundsuggestedresponse_model():
    try:
        return django_apps.get_model(settings.INPUT_COLLECTEDINPUT_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "INPUT_BOUNDSUGGESTEDRESPONSE_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "INPUT_BOUNDSUGGESTEDRESPONSE_MODEL refers to model '%s' that has not been installed"
            % settings.INPUT_COLLECTEDINPUT_MODEL
        )


def lazy_clone(obj, exclude=[], **updates):
    if "id" not in exclude:
        exclude.append("id")
    Model = obj.__class__
    attrs = Model.objects.filter(pk=obj.pk).values().get()
    for k in exclude:
        del attrs[k]
    attrs.update(updates)
    return Model.objects.create(**attrs)


def isolate_response_policy(instrument):
    """
    Ensures the response_policy instance is unique to this CollectionInstrument and marked for
    disallowing future reuse.  If ``instrument`` is the only instance related to its
    ResponsePolicy (i.e., the policy is already isolated), then no work is performed.
    """
    policy = instrument.response_policy
    has_other_uses = policy.collectioninstrument_set.exclude(pk=instrument.pk).exists()
    if has_other_uses:
        instrument.response_policy = clone_response_policy(policy, isolate=True)
        instrument.save()


def clone_response_policy(response_policy, isolate=None, **kwargs):
    """
    Creates a new ResponsePolicy with identical flags.  All kwargs are forwarded to the manager's
    create() method to allow for easy overrides.
    """

    from ..models.collection import ResponsePolicy

    if "is_singleton" not in kwargs:
        if isolate is None:
            isolate = response_policy.is_singleton
        kwargs["is_singleton"] = isolate

    if "nickname" not in kwargs:
        nickname = "Cloned pk={pk}, {kwargs!r}".format(
            **{
                "pk": response_policy.pk,
                "kwargs": kwargs,  # includes processed 'is_singletone' value
            }
        )

        # Trim to max length
        max_length = response_policy._meta.get_field("nickname").max_length
        overflow_count = len(nickname[max_length:])
        if overflow_count:
            nickname = nickname[: -(3 + overflow_count)] + "..."

    # Get a clean set of kwargs where the called ``**kwargs`` override the defaults.
    create_kwargs = response_policy.get_flags()
    create_kwargs.update(kwargs)

    policy = ResponsePolicy.objects.create(**create_kwargs)
    return policy


def clone_collection_request(collection_request):
    from . import CollectionInstrument, CollectionRequest

    common_excludes = ["date_created", "date_modified"]
    cloned = lazy_clone(collection_request, exclude=common_excludes)
    for instrument in collection_request.collectioninstrument_set.all():
        cloned_instrument = lazy_clone(
            instrument,
            exclude=common_excludes,
            **{
                "collection_request_id": cloned.id,
            },
        )
        for condition in instrument.conditions.all():
            lazy_clone(
                condition,
                exclude=common_excludes,
                **{
                    "instrument_id": cloned_instrument.id,
                    "data_getter": re.sub(
                        r"^instrument:\d+$",
                        "instrument:%d" % cloned_instrument.id,
                        condition.data_getter,
                    ),
                },
            )
        for bound_response in instrument.bound_suggested_responses.all():
            lazy_clone(bound_response, collection_instrument_id=cloned_instrument.id)

    return cloned


class ConditionNode(Q):
    AND = ", "
    OR = " | "

    def __str__(self):
        joiner = self.connector
        nodes = flatten(self)
        if not nodes:
            return ""
        if len(nodes) > 1:
            wrapper = "(%s)"
        else:
            wrapper = "%s"
        # if self.negated:
        #     wrapper = 'NOT%s' % wrapper
        return force_str(wrapper % joiner.join(force_str(c) for c in nodes))

    def __iter__(self):
        return iter(self.children)


def flatten(items):
    # TODO: Block recursion
    from .conditions import ConditionGroup, Case

    if isinstance(items, Case):
        return items

    # if isinstance(items, ConditionGroup):
    #     parent_groups.append(items)

    items = list(items)
    if len(items) == 0:
        return items

    # size = len(items)
    bit = items[0]
    if isinstance(bit, Iterable) and not isinstance(bit, str):
        return flatten(bit) + flatten(items[1:])
    return sorted([bit] + flatten(items[1:]))
