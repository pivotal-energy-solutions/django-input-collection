"""answer_index.py: prefetched answers for instrument: conditions, keyed by request and measure."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from collections import defaultdict


class AnswerIndex:
    """What InstrumentResolver would read from the database, held in memory.

    Contract: ``inputs`` must already be filtered the way the resolving collector filters
    (``filter_for_context(**collector.context)`` then ``collector.filter_condition_inputs``).
    ``lookup`` bypasses both, so an input passed here is seen and one left out is not. Build one
    index per filter (e.g. per role), never share one between collectors that filter differently.

    ``instruments`` should come from ``load_instruments`` (Meta ordering per request, bound
    responses prefetched); requests with no instrument here defer to the database. Pass
    ``complete=True`` only when they are every instrument of their requests: a gate missing from
    a covered request then raises DoesNotExist from memory, as the database path would.
    """

    def __init__(self, instruments, inputs, *, complete=False):
        self.complete = complete
        self._by_request = defaultdict(dict)  # request id -> measure_id -> first instrument
        self._by_pk = {}
        for instrument in instruments:
            self._by_request[instrument.collection_request_id].setdefault(
                instrument.measure_id, instrument
            )
            self._by_pk[instrument.pk] = instrument
        self._values = defaultdict(list)  # instrument id -> [data, ...]
        for row in inputs:
            self._values[row.instrument_id].append(row.data)

    def covers(self, request_ids) -> bool:
        return all(request_id in self._by_request for request_id in request_ids)

    def _candidates(self, request_ids, parent_pk, measure):
        if parent_pk:
            instrument = self._by_pk.get(int(parent_pk))
            if instrument is None or instrument.collection_request_id != request_ids[0]:
                return None
            return [instrument]
        found = [self._by_request[r].get(measure) for r in request_ids]
        return [instrument for instrument in found if instrument is not None]

    def lookup(self, requests, parent_pk=None, measure=None):
        """(values, suggested values) like InstrumentResolver, or None to defer to the database."""
        request_ids = [getattr(r, "pk", r) for r in requests]
        if not request_ids or not self.covers(request_ids):
            return None
        candidates = self._candidates(request_ids, parent_pk, measure)
        if not candidates:
            if self.complete:
                from ..models import CollectionInstrument

                raise CollectionInstrument.DoesNotExist(
                    f"No gating instrument {parent_pk or measure!r}"
                )
            return None  # partial index: let the database decide
        for instrument in candidates:
            values = self._values.get(instrument.pk)
            if values:
                return list(values), self._suggested(instrument)
        return [], self._suggested(candidates[0])

    @staticmethod
    def _suggested(instrument):
        # Bound rows are prefetched by load_instruments; the M2M would cost a query here.
        return [
            bound.suggested_response.data for bound in instrument.bound_suggested_responses.all()
        ]
