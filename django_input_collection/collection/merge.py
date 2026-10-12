"""merge.py: one checklist across several collection requests, read in a fixed number of queries."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import operator
from collections import defaultdict
from collections.abc import Callable
from functools import reduce

from django.db.models import Prefetch

from ..managers.collected_input import CollectedInputQuerySet
from ..managers.collection_instrument import CONDITION_PREFETCH
from .answer_index import AnswerIndex, filter_key
from .repeat import question_key, read_context
from .merged_checklist import (  # noqa: F401 (re-exported: the public names are collection.merge.*)
    GENERAL,
    MergedChecklist,
    MergedQuestion,
    MergedSection,
    section_name,
)

# owner(measure_id, instruments in request order, newest answer or None) -> the instrument shown
Owner = Callable[[str, tuple, object], object]


def bound_responses_prefetch():
    """Bound rows in binding order (pk): the order the program defines its choices."""
    from ..models import get_boundsuggestedresponse_model

    bound = get_boundsuggestedresponse_model().objects.select_related("suggested_response")
    return Prefetch("bound_suggested_responses", queryset=bound.order_by("pk"))


def instrument_prefetch() -> tuple:
    # Suggested values come from the bound rows; the plain suggested_responses M2M is not prefetched.
    return (bound_responses_prefetch(), *CONDITION_PREFETCH)


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
        .select_related("group", "type", "response_policy", "measure", "repeat_group")
        .prefetch_related(*instrument_prefetch())
        .order_by("collection_request_id", *CollectionInstrument._meta.ordering)
    )
    share_requests(instruments, [r for r in requests if not isinstance(r, int)])
    return instruments


def load_condition_instruments(request, others) -> tuple[list, list]:
    """``load_instruments`` over ``request`` plus ``others``, and the requests that have any.

    ``others`` is requests or pks, or a CollectionRequest QuerySet: a QuerySet is folded into the
    one instrument query as a subquery, its requests come back on the instrument rows, and its
    ``order_by`` (single-valued fields of the request) orders them, so it costs no query. Returns
    ``(instruments, [request, *others])``: others in their order, as given (a QuerySet's as
    objects), less ``request`` itself and any with no instrument.
    """
    from django.db.models import QuerySet

    order = _subquery_order(others) if isinstance(others, QuerySet) else None
    if order is None:
        given = {}  # pk -> request as given, first occurrence wins
        for other in others:
            if _pk(other) != request.pk:
                given.setdefault(_pk(other), other)
        instruments = load_instruments([request, *given])
        share_requests(instruments, [r for r in given.values() if not isinstance(r, int)])
        found = {i.collection_request_id for i in instruments}
        return instruments, [request, *[r for pk, r in given.items() if pk in found]]
    instruments = _load_with_subquery(request, others, order)
    first = {}  # other request id -> (its order values, request)
    for instrument in instruments:
        if instrument.collection_request_id != request.pk:
            values = tuple(getattr(instrument, f"_load_order_{i}") for i in range(len(order)))
            first.setdefault(
                instrument.collection_request_id, (values, instrument.collection_request)
            )
    ordered = list(first.values())
    for position in reversed(range(len(order))):  # stable sorts, last key first
        ordered.sort(
            key=lambda v: (v[0][position] is None, v[0][position]), reverse=order[position][1]
        )
    requests = [request, *[r for _values, r in ordered]]
    share_requests(instruments, requests)  # one object per request
    return instruments, requests


def _pk(request):
    return getattr(request, "pk", request)


def _subquery_order(queryset):
    """[(request field, descending), ...] ending in pk, or None when it can't ride a subquery."""
    if queryset.query.is_sliced:
        return None
    fields = queryset.query.order_by
    if not fields and queryset.query.default_ordering:
        fields = queryset.model._meta.ordering
    order = []
    for field in fields:
        if not isinstance(field, str) or field == "?" or "." in field:
            return None  # an expression or raw SQL: evaluate the queryset instead
        order.append((field.lstrip("-"), field.startswith("-")))
    return [*order, ("pk", False)]


def _load_with_subquery(request, others, order):
    from django.db.models import F, Q

    from ..models import CollectionInstrument

    annotations = {
        f"_load_order_{i}": F(f"collection_request__{field}") for i, (field, _d) in enumerate(order)
    }
    return list(
        CollectionInstrument.objects.filter(
            Q(collection_request_id=request.pk)
            | Q(collection_request_id__in=others.order_by().values("pk"))
        )
        .select_related(
            "group", "type", "response_policy", "measure", "repeat_group", "collection_request"
        )
        .annotate(**annotations)
        .prefetch_related(*instrument_prefetch())
        .order_by("collection_request_id", *CollectionInstrument._meta.ordering)
    )


def share_requests(instruments, requests):
    """Point instruments at the caller's request objects, so per-request caches (e.g. a reverse
    one-to-one to the request's owner) are hit once per request, not once per instrument."""
    by_id = {request.pk: request for request in requests}
    for instrument in instruments:
        request = by_id.get(instrument.collection_request_id)
        if request is not None:
            instrument.collection_request = request


def share_repeat_groups(instruments) -> list:
    """One RepeatGroup object per group (select_related builds one per row), its condition tree
    prefetched: a query per prefetch level when any instrument is repeated, none otherwise.

    Instruments not loaded by ``load_instruments`` (``merge_requests(instruments=...)``) get
    their groups in one query, so neither expansion nor a copy-scoped AnswerIndex lookup loads
    ``instrument.repeat_group`` per instrument.
    """
    from django.db.models import prefetch_related_objects

    repeated = [i for i in instruments if getattr(i, "repeat_group_id", None) is not None]
    if not repeated:
        return []
    prefetch_related_objects(repeated, "repeat_group")  # no query when select_related loaded it
    groups = {}
    for instrument in repeated:
        instrument.repeat_group = groups.setdefault(
            instrument.repeat_group_id, instrument.repeat_group
        )
    prefetch_related_objects(list(groups.values()), *CONDITION_PREFETCH)
    return list(groups.values())


def filter_per_copy(inputs, context, indices=None, narrow=None) -> list:
    """``narrow(inputs.filter_for_context(**context))`` rows, oldest first, with each copy
    filtered on its own: unrepeated rows, then each repeat index in ``indices``.

    A ``filter_for_context`` that keeps the newest row per instrument (as
    UserLatestCollectedInputQuerySet does) would otherwise keep one row across all of an
    instrument's copies. ``indices`` None (no repeat group): one plain filter, as before. The
    partitions are OR'd into one query; if they can't be combined (e.g. a union()ed
    filter), each is read on its own.
    """
    narrow = narrow or (lambda queryset: queryset)
    if indices is None:
        return _ordered(narrow(inputs.filter_for_context(**context)))
    partitions = [{"repeat_index__isnull": True}, *({"repeat_index": n} for n in sorted(indices))]
    parts = [narrow(inputs.filter(**rows).filter_for_context(**context)) for rows in partitions]
    try:
        combined = reduce(operator.or_, parts)
    except (TypeError, AssertionError):  # Django refuses to combine these querysets
        rows = [row for part in parts for row in part]
        return sorted(rows, key=lambda row: (row.date_created, row.pk))
    return _ordered(combined)


def copy_indices(instruments, rows):
    """The repeat indices ``rows`` hold, or None when no instrument is repeated."""
    if not any(getattr(i, "repeat_group_id", None) is not None for i in instruments):
        return None
    return {row.repeat_index for row in rows if getattr(row, "repeat_index", None) is not None}


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
    """(question key -> newest row, (instrument id, repeat index) -> its rows oldest first).

    A row's key is its measure, or ``measure#n`` for copy n: newest per (measure, repeat_index).
    """
    measure_of = {instrument.pk: instrument.measure_id for instrument in instruments}
    answers, by_instrument = {}, defaultdict(list)
    for row in rows:  # oldest first: the newest per key wins
        if row.instrument_id in measure_of:
            repeat_index = getattr(row, "repeat_index", None)
            answers[question_key(measure_of[row.instrument_id], repeat_index)] = row
            by_instrument[(row.instrument_id, repeat_index)].append(row)
    return answers, by_instrument


def _filters_nothing(collector, queryset) -> bool:
    return (
        not read_context(collector.context)  # a write copy never narrows a gate read
        and collector.condition_cache_key() is None
        and type(queryset).filter_for_context is CollectedInputQuerySet.filter_for_context
    )


def _indexes(requests, collectors, inputs, rows, build, indices=None):
    """request id -> AnswerIndex over ``inputs`` as that request's collector filters them.

    Collectors that filter alike share one index (one read; none when the filter is a no-op),
    bound to that filter key. ``indices`` (``copy_indices``) filters each copy on its own.
    """
    by_key, indexes = {}, {}
    for request in requests:
        collector = collectors[request.pk]
        key = filter_key(collector)
        if key not in by_key:
            if _filters_nothing(collector, inputs):
                by_key[key] = build(rows, collector)
            else:
                filtered = filter_per_copy(
                    inputs,
                    read_context(collector.context),
                    indices,
                    narrow=collector.filter_condition_inputs,
                )
                by_key[key] = build(filtered, collector)
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

    Repeat groups: each group's live copies are resolved once by its request's collector
    (``resolve_repeat``) and each repeated measure becomes one question per copy, keyed
    ``measure#n`` (see MergedChecklist). Each collector's index reads every copy's rows through
    its filters copy by copy (``filter_per_copy``); a ``condition_inputs`` override must keep
    each copy's rows the same way.
    """
    requests = list(requests)
    complete = instruments is None
    instruments = load_instruments(requests) if complete else list(instruments)
    share_repeat_groups(instruments)
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
        indices = copy_indices(instruments, rows)
        indexes = _indexes(requests, collectors, inputs, rows, build, indices)
    return MergedChecklist(
        requests, collectors, by_request, answers, indexes, owner, answer_rows=answer_rows
    )


def __getattr__(name):
    if name == "INSTRUMENT_PREFETCH":  # pre-11.0.2 name; built lazily (needs the bound model)
        return instrument_prefetch()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
