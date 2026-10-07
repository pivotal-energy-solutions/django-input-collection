"""merge.py: one checklist across several collection requests, read in a fixed number of queries."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from collections import defaultdict
from collections.abc import Callable

from ..managers.collected_input import CollectedInputQuerySet
from ..managers.collection_instrument import CONDITION_PREFETCH
from .answer_index import AnswerIndex
from .merged_checklist import (  # noqa: F401 (re-exported: the public names are collection.merge.*)
    GENERAL,
    MergedChecklist,
    MergedQuestion,
    MergedSection,
    section_name,
)
from .resolvers import _freeze

# owner(measure_id, instruments in request order, newest answer or None) -> the instrument shown
Owner = Callable[[str, tuple, object], object]

# Suggested values come from the bound rows; the plain suggested_responses M2M is not prefetched.
INSTRUMENT_PREFETCH = (
    "bound_suggested_responses__suggested_response",
    *CONDITION_PREFETCH,
)


def load_instruments(requests) -> list:
    """Every instrument of ``requests`` with responses, bound flags and condition trees prefetched.

    Ordered by request, then ``CollectionInstrument.Meta.ordering`` within each request, so the
    first instrument per measure is the one ``InstrumentResolver`` would pick. Sort a copy for
    display; build an AnswerIndex from this order. The ``suggested_responses`` M2M is not
    prefetched (read ``bound_suggested_responses``): touching it costs a query per instrument.
    """
    from ..models import CollectionInstrument

    request_ids = [getattr(r, "pk", r) for r in requests]
    instruments = list(
        CollectionInstrument.objects.filter(collection_request_id__in=request_ids)
        .select_related("group", "type", "response_policy", "measure")
        .prefetch_related(*INSTRUMENT_PREFETCH)
        .order_by("collection_request_id", *CollectionInstrument._meta.ordering)
    )
    share_requests(instruments, [r for r in requests if not isinstance(r, int)])
    return instruments


def share_requests(instruments, requests):
    """Point instruments at the caller's request objects, so per-request caches (e.g. a reverse
    one-to-one to the request's owner) are hit once per request, not once per instrument."""
    by_id = {request.pk: request for request in requests}
    for instrument in instruments:
        request = by_id.get(instrument.collection_request_id)
        if request is not None:
            instrument.collection_request = request


def first_owner(measure_id, instruments, answer):
    """Default owner: the first request (in the caller's order) that asks the measure."""
    return instruments[0]


def _default_inputs(requests):
    from ..models import get_input_model

    return get_input_model().objects.filter(collection_request__in=[r.pk for r in requests])


def _newest_answers(rows, instruments) -> dict:
    measure_of = {instrument.pk: instrument.measure_id for instrument in instruments}
    answers = {}
    for row in rows:  # oldest first: the newest per measure wins
        if row.instrument_id in measure_of:
            answers[measure_of[row.instrument_id]] = row
    return answers


def _filters_nothing(collector, queryset) -> bool:
    return (
        not collector.context
        and collector.condition_cache_key() is None
        and type(queryset).filter_for_context is CollectedInputQuerySet.filter_for_context
    )


def _index_rows(requests, collectors, inputs, rows):
    """Rows for the AnswerIndex, filtered as the collectors filter, or None to read the database.

    Without ``condition_inputs`` the index can stand in only when every collector filters alike;
    then it reads ``inputs`` through that filter (reusing ``rows`` when the filter is a no-op).
    """
    signatures = set()
    for request in requests:
        collector = collectors[request.pk]
        try:
            signatures.add((collector.condition_cache_key(), _freeze(collector.context)))
        except TypeError:
            return None
    if len(signatures) != 1:
        return None  # collectors filter differently: no shared index (contract of AnswerIndex)
    collector = collectors[requests[0].pk]
    if _filters_nothing(collector, inputs):
        return rows
    filtered = collector.filter_condition_inputs(inputs.filter_for_context(**collector.context))
    return list(filtered.order_by("date_created", "id"))


def merge_requests(
    requests, *, collectors, inputs=None, condition_inputs=None, owner=first_owner, instruments=None
):
    """One checklist over ``requests`` (in priority order): one question per measure.

    ``collectors`` maps request id -> that request's collector; conditions are evaluated by each
    instrument's own collector. ``inputs`` (default: every input on the requests) give answers,
    newest per measure. ``condition_inputs`` must already be filtered as the collectors filter
    (see AnswerIndex); without it the index is derived when every collector filters alike.
    ``owner(measure_id, instruments, answer)`` picks which instrument a shared measure shows.
    """
    requests = list(requests)
    complete = instruments is None
    instruments = load_instruments(requests) if complete else list(instruments)
    by_request = defaultdict(list)
    for instrument in instruments:
        by_request[instrument.collection_request_id].append(instrument)

    inputs = _default_inputs(requests) if inputs is None else inputs
    rows = list(inputs.order_by("date_created", "id"))
    answers = _newest_answers(rows, instruments)
    if condition_inputs is not None:
        index_rows = list(condition_inputs.order_by("date_created", "id"))
    else:
        index_rows = _index_rows(requests, collectors, inputs, rows)
    index = None
    if index_rows is not None:
        index = AnswerIndex(instruments, index_rows, complete=complete)
    return MergedChecklist(requests, collectors, by_request, answers, index, owner)
