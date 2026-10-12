"""Repeat-group fixtures: a doors checklist, group membership, per-copy answers."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from ..models import RepeatGroup
from . import factories
from .checklists import gate, question


def repeat_group(
    request,
    slug="doors",
    count_source="instrument:door-count",
    max_count=5,
    label="",
    name="Doors",
    order=0,
):
    return RepeatGroup.objects.create(
        collection_request=request,
        slug=slug,
        name=name,
        count_source=count_source,
        max_count=max_count,
        label=label,
        order=order,
    )


def in_group(instrument, group):
    instrument.repeat_group = group
    instrument.save(update_fields=["repeat_group"])
    return instrument


def answer(instrument, data, repeat_index=None):
    return factories.CollectedInputFactory.create(
        instrument=instrument,
        collection_request=instrument.collection_request,
        data=data,
        repeat_index=repeat_index,
    )


def group_gate(group, parent_measure, match_data="yes"):
    """A condition on the whole group (no instrument): shown when parent_measure == match_data."""
    case = factories.CaseFactory.create(match_type="match", match_data=match_data)
    condition_group = factories.ConditionGroupFactory.create(
        requirement_type="all-pass", cases=[case]
    )
    return factories.ConditionFactory.create(
        instrument=None,
        repeat_group=group,
        condition_group=condition_group,
        data_getter=f"instrument:{parent_measure}",
    )


def doors(request=None, count=None, **group_kwargs):
    """Section "Doors": door-count (1), the "doors" group — door-type (2), door-glazed (3),
    door-glazing-area (4, shown when door-glazed is "yes") — then after-doors (5).

    ``count`` answers door-count (as text, like a stored input). Returns
    ``(request, group, {measure_id: instrument})``.
    """
    request = request or factories.CollectionRequestFactory.create()
    found = {"door-count": question(request, "door-count", group="Doors", order=1)}
    group = repeat_group(request, **group_kwargs)
    found["door-type"] = in_group(
        question(request, "door-type", group="Doors", order=2, responses=("Solid", "Full-lite")),
        group,
    )
    found["door-glazed"] = in_group(
        question(request, "door-glazed", group="Doors", order=3, responses=("yes", "no")), group
    )
    found["door-glazing-area"] = in_group(
        question(request, "door-glazing-area", group="Doors", order=4), group
    )
    gate(found["door-glazing-area"], "door-glazed")
    found["after-doors"] = question(request, "after-doors", group="Doors", order=5)
    if count is not None:
        answer(found["door-count"], str(count))
    return request, group, found
