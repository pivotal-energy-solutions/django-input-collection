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
    answer: object = None


@dataclass
class MergedSection:
    name: str
    order: int
    questions: list = field(default_factory=list)


def section_name(instrument) -> str:
    return instrument.group_id or GENERAL


def request_sections(instruments) -> list[str]:
    """One request's section names in its own order (min instrument order; General first)."""
    first_order = {}
    for instrument in instruments:
        name = section_name(instrument)
        key = -1 if name == GENERAL else (instrument.order or 0)
        first_order[name] = min(first_order.get(name, key), key)
    return sorted(first_order, key=first_order.get)  # stable: ties keep first-seen order


class MergedChecklist:
    """``requests`` read as one checklist. Build with ``merge_requests``."""

    def __init__(self, requests, collectors, by_request, answers, index, owner):
        self.requests = list(requests)
        self.collectors = collectors
        self.answers = answers
        self.index = index
        self._position = {request.pk: n for n, request in enumerate(self.requests)}
        self._children_map = None
        self.questions = self._questions(by_request, owner)
        self.sections = self._sections(by_request)

    def _questions(self, by_request, owner) -> dict:
        entries = defaultdict(list)
        for request in self.requests:
            for instrument in by_request.get(request.pk, ()):
                entries[instrument.measure_id].append(instrument)
        questions = {}
        for measure_id, instruments in entries.items():
            answer = self.answers.get(measure_id)
            chosen = owner(measure_id, tuple(instruments), answer)
            questions[measure_id] = MergedQuestion(
                measure_id, chosen, tuple(instruments), section_name(chosen), answer
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
            items = sorted(buckets[name], key=self._question_key)
            if items:
                sections.append(MergedSection(name, len(sections), items))
        return sections

    def _question_key(self, question):
        instrument = question.instrument
        position = self._position[instrument.collection_request_id]
        return position, instrument.order or 0, instrument.pk

    def owner(self, measure_id):
        return self.questions[measure_id].instrument

    def evaluate(self, measures=None) -> dict:
        """measure_id -> True if any request's instrument is allowed; None if none could say."""
        measures = list(self.questions) if measures is None else measures
        with read_pass(index=self.index):
            return {
                measure_id: self._visible(self.questions[measure_id]) for measure_id in measures
            }

    def _visible(self, question):
        results = []
        for instrument in question.instruments:
            collector = self.collectors[instrument.collection_request_id]
            try:
                results.append(collector.is_instrument_allowed(instrument))
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
            policy = question.instrument.response_policy
            required = bool(policy and policy.required)
            progress["total"] += 1
            progress["visible"] += bool(visibility.get(question.measure_id))
            progress["required_total"] += required
            if question.answer is not None:
                progress["answered"] += 1
                progress["required_answered"] += required
        return progress
