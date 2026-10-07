"""merge.py: one checklist across several collection requests, read in a fixed number of queries."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from collections import defaultdict
from collections.abc import Callable

from ..managers.collected_input import CollectedInputQuerySet
from ..managers.collection_instrument import CONDITION_PREFETCH
from .answer_index import AnswerIndex, filter_key
from .merged_checklist import (  # noqa: F401 (re-exported: the public names are collection.merge.*)
    GENERAL,
    MergedChecklist,
    MergedQuestion,
    MergedSection,
    section_name,
)

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
    """Default owner: the request already holding the answer, else the first request asking it."""
    if answer is not None:
        for instrument in instruments:
            if instrument.collection_request_id == answer.collection_request_id:
                return instrument
    return instruments[0]


def _default_inputs(requests):
    from ..models import get_input_model

    return get_input_model().objects.filter(collection_request__in=[r.pk for r in requests])


def _ordered(queryset) -> list:
    return list(queryset.order_by("date_created", "id"))


def _newest_answers(rows, instruments) -> tuple[dict, dict]:
    """(measure_id -> newest row, instrument id -> its rows oldest first)."""
    measure_of = {instrument.pk: instrument.measure_id for instrument in instruments}
    answers, by_instrument = {}, defaultdict(list)
    for row in rows:  # oldest first: the newest per measure wins
        if row.instrument_id in measure_of:
            answers[measure_of[row.instrument_id]] = row
            by_instrument[row.instrument_id].append(row)
    return answers, by_instrument


def _filters_nothing(collector, queryset) -> bool:
    return (
        not collector.context
        and collector.condition_cache_key() is None
        and type(queryset).filter_for_context is CollectedInputQuerySet.filter_for_context
    )


def _indexes(requests, collectors, inputs, rows, build):
    """request id -> AnswerIndex over ``inputs`` as that request's collector filters them.

    Collectors that filter alike share one index (one read; none when the filter is a no-op),
    bound to that filter key.
    """
    by_key, indexes = {}, {}
    for request in requests:
        collector = collectors[request.pk]
        key = filter_key(collector)
        if key not in by_key:
            if _filters_nothing(collector, inputs):
                by_key[key] = build(rows, collector)
            else:
                filtered = inputs.filter_for_context(**collector.context)
                by_key[key] = build(
                    _ordered(collector.filter_condition_inputs(filtered)), collector
                )
        indexes[request.pk] = by_key[key]
    return indexes


def merge_requests(
    requests, *, collectors, inputs=None, condition_inputs=None, owner=first_owner, instruments=None
):
    """One checklist over ``requests`` (in priority order): one question per measure.

    ``collectors`` maps request id -> that request's collector; each instrument's conditions are
    evaluated by its own request's collector. ``inputs`` (default: every input on the requests)
    give the answers, newest per measure by (date_created, id). ``owner(measure_id, instruments,
    answer)`` picks the instrument a shared measure shows (default: ``first_owner``).

    Conditions read an AnswerIndex in ``newest_across`` mode: a measure-based ``instrument:``
    condition sees the same answer the checklist displays (newest across the requests its
    collector searches), not its own request's first; pk-based conditions stay in their request.
    ``condition_inputs`` must already be filtered as the collectors filter (see AnswerIndex).
    Without it each collector's index reads ``inputs`` through that collector's filters, so an
    ``inputs`` override that narrows rows narrows what conditions see too. Each question's
    ``answers`` are every row of the instrument holding its newest ``answer`` (a multi-value
    answer whole). They come from ``inputs``: they are the rows its conditions read when
    conditions read the same rows, not when ``condition_inputs`` or a collector's filters narrow
    what conditions read.

    Partial-index mode: with ``instruments=`` given, a condition searching a request those
    instruments don't cover falls back to the database lookup, which reads its own request
    first, not the newest across requests. "Condition reads the displayed answer" then holds
    only for covered requests.
    """
    requests = list(requests)
    complete = instruments is None
    instruments = load_instruments(requests) if complete else list(instruments)
    by_request = defaultdict(list)
    for instrument in instruments:
        by_request[instrument.collection_request_id].append(instrument)

    inputs = _default_inputs(requests) if inputs is None else inputs
    rows = _ordered(inputs)
    answers, answer_rows = _newest_answers(rows, instruments)

    def build(index_rows, collector=None):
        return AnswerIndex(
            instruments, index_rows, complete=complete, newest_across=True, collector=collector
        )

    if condition_inputs is not None:
        # The caller vouches for every collector's filters: unbound.
        shared = build(_ordered(condition_inputs))
        indexes = dict.fromkeys((request.pk for request in requests), shared)
    else:
        indexes = _indexes(requests, collectors, inputs, rows, build)
    return MergedChecklist(
        requests, collectors, by_request, answers, indexes, owner, answer_rows=answer_rows
    )
