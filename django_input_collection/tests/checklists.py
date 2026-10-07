"""Synthetic checklists for query-count and merge tests: gated questions, flags, answers."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from . import factories


def gate(child, parent_measure, match_type="match", match_data="yes"):
    case = factories.CaseFactory.create(match_type=match_type, match_data=match_data)
    group = factories.ConditionGroupFactory.create(requirement_type="all-pass", cases=[case])
    return factories.ConditionFactory.create(
        instrument=child, condition_group=group, data_getter=f"instrument:{parent_measure}"
    )


def question(collection_request, measure, group="Section A", order=0, responses=()):
    instrument = factories.CollectionInstrumentFactory.create(
        collection_request=collection_request,
        measure=factories.MeasureFactory.create(id=measure),
        group=factories.CollectionGroupFactory.create(id=group),
        order=order,
    )
    for value in responses:
        factories.BoundSuggestedResponseFactory.create(
            collection_instrument=instrument,
            suggested_response=factories.SuggestedResponseFactory.create(data=value),
        )
    return instrument


def build_checklist(size, collection_request=None, prefix="q", answer=True):
    """A gate question plus ``size`` children gated on it (even ones pass), each with two responses."""
    collection_request = collection_request or factories.CollectionRequestFactory.create()
    parent = question(collection_request, f"{prefix}-gate", responses=("yes", "no"))
    if answer:
        factories.CollectedInputFactory.create(
            instrument=parent, collection_request=collection_request, data="yes"
        )
    for i in range(size):
        child = question(collection_request, f"{prefix}-{i}", order=i + 1, responses=("a", "b"))
        gate(child, parent.measure_id, match_data="yes" if i % 2 == 0 else "no")
    return collection_request
