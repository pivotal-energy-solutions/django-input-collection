"""merged_checklist.py: the result of merge_requests — one question per measure across requests."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from collections import defaultdict
from dataclasses import dataclass, field

from .resolvers import read_pass

GENERAL = "General"


@dataclass
class MergedQuestion:
    measure_id: str
    instrument: object  # the owner's
    instruments: tuple  # every request's, in request order
    section: str
    answer: object = None  # the newest row across the requests
    # Every row of the answering instrument, oldest first: what its conditions read.
    answers: list = field(default_factory=list)

    @property
    def is_required(self):
        """Required if any request requires it; None only when no instrument has a policy."""
        policies = [i.response_policy for i in self.instruments or (self.instrument,)]
        policies = [policy for policy in policies if policy]
        return any(policy.required for policy in policies) if policies else None


@dataclass
class MergedSection:
    name: str
    order: int
    questions: list = field(default_factory=list)


def section_name(instrument) -> str:
    return instrument.group_id or GENERAL


def request_sections(instruments) -> list[str]:
    """One request's section names in its own order: General first, then by each section's
    first instrument in display order ``(order or 0, pk)``, as the mixin orders them."""
    first_order = {}
    for instrument in instruments:
        name = section_name(instrument)
        key = (-1, 0) if name == GENERAL else (instrument.order or 0, instrument.pk)
        first_order[name] = min(first_order.get(name, key), key)
    return sorted(first_order, key=first_order.get)


class MergedChecklist:
    """``requests`` read as one checklist. Build with ``merge_requests``."""

    def __init__(self, requests, collectors, by_request, answers, indexes, owner, answer_rows=None):
        self.requests = list(requests)
        self.collectors = collectors
        self.answers = answers
        self._indexes = indexes  # request id -> AnswerIndex its collector reads
        shared = {id(index) for index in indexes.values()}
        # The one index every collector reads; None when collectors filter differently.
        self.index = next(iter(indexes.values())) if len(shared) == 1 else None
        self._position = {request.pk: n for n, request in enumerate(self.requests)}
        self._children_map = None
        self.questions = self._questions(by_request, owner, answer_rows or {})
        self.sections = self._sections(by_request)

    def _questions(self, by_request, owner, answer_rows) -> dict:
        entries = defaultdict(list)
        for request in self.requests:
            for instrument in by_request.get(request.pk, ()):
                entries[instrument.measure_id].append(instrument)
        questions = {}
        for measure_id, instruments in entries.items():
            answer = self.answers.get(measure_id)
            chosen = owner(measure_id, tuple(instruments), answer)
            rows = (
                list(answer_rows.get(answer.instrument_id, (answer,))) if answer is not None else []
            )
            questions[measure_id] = MergedQuestion(
                measure_id, chosen, tuple(instruments), section_name(chosen), answer, rows
            )
        return questions

    def _sections(self, by_request) -> list:
        names = []
        for request in self.requests:
            for name in request_sections(by_request.get(request.pk, ())):
                if name not in names:
                    names.append(name)
        buckets = {name: [] for name in names}
        for question in self.questions.values():
            buckets[question.section].append(question)
        sections = []
        for name in names:
            items = self._follow_parents(sorted(buckets[name], key=self._question_key))
            if items:
                sections.append(MergedSection(name, len(sections), items))
        return sections

    def _question_key(self, question):
        instrument = question.instrument
        position = self._position[instrument.collection_request_id]
        return position, instrument.order or 0, instrument.pk

    def _follow_parents(self, items) -> list:
        """A question gated on another request's question in this section sits right after it;
        a request's own order already places its dependants (Steven, 2026-10-08)."""
        here = {q.measure_id: q for q in items}
        children = self._children()
        parent_of = {}
        for question in items:
            for child in children.get(question.measure_id, ()):
                parent_of.setdefault(child, question.measure_id)  # the earliest parent wins
        movers = set()
        grown = True
        while grown:  # to a fixed point: a child may sort before its moved parent
            grown = False
            for question in items:
                if question.measure_id in movers:
                    continue
                parent = here.get(parent_of.get(question.measure_id))
                if parent is None:
                    continue
                crosses = (
                    parent.instrument.collection_request_id
                    != question.instrument.collection_request_id
                )
                if crosses or parent.measure_id in movers:  # a moved parent takes its chain along
                    movers.add(question.measure_id)
                    grown = True
        if not movers:
            return items
        placed, seen = [], set()

        def place(question):
            if question.measure_id in seen:
                return
            seen.add(question.measure_id)
            placed.append(question)
            for child in items:
                if (
                    child.measure_id in movers
                    and parent_of[child.measure_id] == question.measure_id
                ):
                    place(child)

        for question in items:
            if question.measure_id not in movers:
                place(question)
        placed.extend(q for q in items if q.measure_id not in seen)  # cycles: keep every question
        return placed

    def owner(self, measure_id):
        return self.questions[measure_id].instrument

    def evaluate(self, measures=None) -> dict:
        """measure_id -> True if any request's instrument is allowed; None if none could say.

        A snapshot: answers are as of when the merge was built. Rebuild with merge_requests after
        writing inputs.
        """
        measures = list(self.questions) if measures is None else measures
        with read_pass(index=self.index):
            return {
                measure_id: self._visible(self.questions[measure_id]) for measure_id in measures
            }

    def _allowed(self, collector, instrument):
        if self.index is not None:
            return collector.is_instrument_allowed(instrument)
        with read_pass(index=self._indexes[instrument.collection_request_id]):
            return collector.is_instrument_allowed(instrument)

    def _visible(self, question):
        results = []
        for instrument in question.instruments:
            collector = self.collectors[instrument.collection_request_id]
            try:
                results.append(self._allowed(collector, instrument))
            except Exception:  # as ChecklistConsumerMixin._get_instrument_visibility
                results.append(None)
        if any(results):
            return True
        return False if results and all(r is False for r in results) else None

    def dependents(self, measure_id) -> list[str]:
        """Measures whose visibility depends, directly or transitively, on ``measure_id``."""
        children = self._children()
        seen, todo = set(), [measure_id]
        while todo:
            for child in children.get(todo.pop(), ()):
                if child not in seen and child != measure_id:
                    seen.add(child)
                    todo.append(child)
        return sorted(seen)

    def _children(self) -> dict:
        if self._children_map is None:
            measure_of_pk = {
                str(i.pk): q.measure_id for q in self.questions.values() for i in q.instruments
            }
            children = defaultdict(set)
            for question in self.questions.values():
                for instrument in question.instruments:
                    for condition in instrument.conditions.all():
                        kind, _, source = condition.data_getter.partition(":")
                        if kind == "instrument":
                            children[measure_of_pk.get(source, source)].add(question.measure_id)
            self._children_map = children
        return self._children_map

    def progress(self, visibility) -> dict:
        keys = ("total", "answered", "visible", "required_total", "required_answered")
        progress = dict.fromkeys(keys, 0)
        for question in self.questions.values():
            shown = visibility.get(question.measure_id) is not False  # unknown still counts
            required = bool(question.is_required) and shown  # as the payload's is_required
            progress["total"] += 1
            progress["visible"] += bool(visibility.get(question.measure_id))
            progress["required_total"] += required
            if question.answer is not None:
                progress["answered"] += 1
                progress["required_answered"] += required
        return progress
