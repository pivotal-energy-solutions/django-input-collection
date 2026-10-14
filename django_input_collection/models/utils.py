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
        return django_apps.get_model(
            settings.INPUT_BOUNDSUGGESTEDRESPONSE_MODEL, require_ready=False
        )
    except ValueError:
        raise ImproperlyConfigured(
            "INPUT_BOUNDSUGGESTEDRESPONSE_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "INPUT_BOUNDSUGGESTEDRESPONSE_MODEL refers to model '%s' that has not been installed"
            % settings.INPUT_BOUNDSUGGESTEDRESPONSE_MODEL
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


_CLONE_EXCLUDES = ("id", "date_created", "date_modified")


def _bulk_clone(model, rows, updates):
    """
    Inserts a copy of each ``.values()`` row with ``updates(row)`` applied, in one query where the
    database hands back the new pks, and returns those pks in ``rows`` order.
    """
    from django.db import connections

    objs = []
    for row in rows:
        attrs = {k: v for k, v in row.items() if k not in _CLONE_EXCLUDES}
        attrs.update(updates(row))
        objs.append(model(**attrs))
    using = model.objects.db
    if connections[using].features.can_return_rows_from_bulk_insert:
        return [obj.pk for obj in model.objects.bulk_create(objs)]
    for obj in objs:
        obj.save(force_insert=True)
    return [obj.pk for obj in objs]


def clone_collection_request(collection_request):
    """A copy of ``collection_request``: its repeat groups, instruments (re-pointed at the cloned
    groups), instrument and group conditions, and bound responses.

    Each kind is read once and inserted in bulk, so a checklist costs a handful of queries rather
    than a few per instrument."""
    from . import CollectionInstrument, Condition, RepeatGroup

    BoundResponse = CollectionInstrument._meta.get_field("bound_suggested_responses").related_model
    cloned = lazy_clone(collection_request, exclude=["date_created", "date_modified"])

    groups = list(collection_request.repeat_groups.order_by("pk").values())
    new_group_pks = _bulk_clone(
        RepeatGroup, groups, lambda row: {"collection_request_id": cloned.id}
    )
    group_map = {row["id"]: pk for row, pk in zip(groups, new_group_pks)}

    instruments = list(collection_request.collectioninstrument_set.order_by("pk").values())
    new_instrument_pks = _bulk_clone(
        CollectionInstrument,
        instruments,
        lambda row: {
            "collection_request_id": cloned.id,
            "repeat_group_id": group_map.get(row["repeat_group_id"]),
        },
    )
    instrument_map = {row["id"]: pk for row, pk in zip(instruments, new_instrument_pks)}

    bound = list(
        BoundResponse.objects.filter(collection_instrument_id__in=instrument_map)
        .order_by("pk")
        .values()
    )
    _bulk_clone(
        BoundResponse,
        bound,
        lambda row: {"collection_instrument_id": instrument_map[row["collection_instrument_id"]]},
    )

    # Every instrument is in the map before conditions are copied: an ``instrument:<pk>`` getter
    # names a (gate) instrument that may come after the one it gates. A condition belongs to one
    # instrument or one repeat group, never both.
    conditions = list(
        Condition.objects.filter(
            Q(instrument_id__in=instrument_map) | Q(repeat_group_id__in=group_map)
        )
        .order_by("pk")
        .values()
    )
    _bulk_clone(
        Condition,
        conditions,
        lambda row: {
            "instrument_id": instrument_map.get(row["instrument_id"]),
            "repeat_group_id": group_map.get(row["repeat_group_id"]),
            "data_getter": _remap_instrument_pk(row["data_getter"], instrument_map),
        },
    )

    return cloned


def _remap_instrument_pk(data_getter, instrument_map):
    """``instrument:<pk>`` -> the clone of that instrument; any other getter as written."""
    match = re.fullmatch(r"instrument:(\d+)", data_getter)
    if match is None or int(match.group(1)) not in instrument_map:
        return data_getter
    return "instrument:%d" % instrument_map[int(match.group(1))]


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
