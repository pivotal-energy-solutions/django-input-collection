"""merge.py: one checklist across several collection requests, read in a fixed number of queries."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from ..managers.collection_instrument import CONDITION_PREFETCH

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
