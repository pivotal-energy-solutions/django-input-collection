"""merged_checklist.py: the result of merge_requests — one question per measure (per live copy
of a repeat group) across requests."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from collections import defaultdict
from dataclasses import dataclass, field, replace

from .repeat import CurrentCopy, copy_scope, question_key, set_repeat_anchor
from .resolvers import read_pass

GENERAL = "General"


@dataclass(frozen=True)
class RepeatInfo:
    """Where a question sits in its repeat group: copy ``index`` of ``count`` live copies."""

    group_slug: str
    group_id: int
    index: int
    count: int  # live N
    label: str
    first: bool  # first question of this copy in display order
    binding: object | None


@dataclass
class GroupState:
    """A repeat group as this read resolved it."""

    group: object  # RepeatGroup
    copies: list  # list[Copy]
    clamped: bool  # the raw count exceeded max_count


@dataclass
class MergedQuestion:
    measure_id: str
    instrument: object  # the owner's
    instruments: tuple  # every request's, in request order
    section: str
    answer: object = None  # the newest row across the requests (for this copy)
    # Every row of the answering instrument (and copy), oldest first: what its conditions read.
    answers: list = field(default_factory=list)
    key: str = ""  # measure_id, or "measure_id#n" for copy n; empty means measure_id
    repeat: RepeatInfo | None = None

    def __post_init__(self):
        if not self.key:
            self.key = self.measure_id

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


def _answer_rows(answer, answer_rows) -> list:
    """Every row of the instrument and copy holding ``answer``, oldest first."""
    if answer is None:
        return []
    slot = (answer.instrument_id, getattr(answer, "repeat_index", None))
    return list(answer_rows.get(slot, (answer,)))


class MergedChecklist:
    """``requests`` read as one checklist. Build with ``merge_requests``.

    ``questions`` is keyed by question key: ``measure_id``, or ``measure_id#n`` for copy n of a
    repeat group (the owner instrument's group). Only live copies 1..N exist; ``answers`` keeps
    the newest row for every (measure, repeat_index), hidden copies included.
    """

    def __init__(self, requests, collectors, by_request, answers, indexes, owner, answer_rows=None):
        self.requests = list(requests)
        self.collectors = collectors
        self.answers = answers  # question key -> newest row
        self._indexes = indexes  # request id -> AnswerIndex its collector reads
        shared = {id(index) for index in indexes.values()}
        # The one index every collector reads; None when collectors filter differently.
        self.index = next(iter(indexes.values())) if len(shared) == 1 else None
        self._position = {request.pk: n for n, request in enumerate(self.requests)}
        self._children_map = None
        self._entries = self._entries_by_measure(by_request)
        self._group_states, self._group_anchor_key = self._resolve_groups()
        self.groups = {}  # slug -> GroupState; request priority: the first slug wins
        for state in self._group_states.values():
            self.groups.setdefault(state.group.slug, state)
        self._owner_group = {}  # measure_id -> its owner's RepeatGroup pk, or None
        self.questions = self._questions(owner, answer_rows or {})
        self.sections = self._sections(by_request)
        self._mark_first()

    def _entries_by_measure(self, by_request) -> dict:
        entries = defaultdict(list)
        for request in self.requests:
            for instrument in by_request.get(request.pk, ()):
                entries[instrument.measure_id].append(instrument)
        return {measure_id: tuple(instruments) for measure_id, instruments in entries.items()}

    def _resolve_groups(self) -> tuple[dict, dict]:
        """(group pk -> GroupState, group pk -> its first instrument's (order, pk)).

        Each group is resolved once, by its own request's collector, in a read pass over that
        request's AnswerIndex: an ``instrument:`` count reads memory, not the database.
        """
        groups, anchors = {}, {}
        for instruments in self._entries.values():
            for instrument in instruments:
                group_id = getattr(instrument, "repeat_group_id", None)
                if group_id is None:
                    continue
                groups.setdefault(group_id, instrument.repeat_group)
                key = (instrument.order or 0, instrument.pk)
                if group_id not in anchors or key < anchors[group_id][0]:
                    anchors[group_id] = (key, instrument)
        states = {}
        for pk, group in groups.items():
            set_repeat_anchor(group, anchors[pk][1])
            collector = self.collectors[group.collection_request_id]
            with read_pass(index=self._indexes[group.collection_request_id]):
                copies = list(collector.resolve_repeat(group))
                states[pk] = GroupState(group, copies, collector.repeat_clamped(group))
        return states, {pk: key for pk, (key, _instrument) in anchors.items()}

    def _questions(self, owner, answer_rows) -> dict:
        questions = {}
        for measure_id, instruments in self._entries.items():
            answer = self.answers.get(measure_id)
            # One owner per measure, shared by all its copies: consumer_payload's by_measure (and
            # owner(key)) rely on every copy of a measure showing the same instrument.
            chosen = owner(measure_id, instruments, answer)
            group_id = getattr(chosen, "repeat_group_id", None)
            self._owner_group[measure_id] = group_id
            state = self._group_states.get(group_id)
            if state is None:
                questions[measure_id] = self._question(
                    measure_id, measure_id, chosen, instruments, answer, answer_rows
                )
                continue
            for copy in state.copies:
                key = question_key(measure_id, copy.index)
                info = RepeatInfo(
                    state.group.slug,
                    state.group.pk,
                    copy.index,
                    len(state.copies),
                    copy.label,
                    False,
                    copy.binding,
                )
                questions[key] = self._question(
                    measure_id, key, chosen, instruments, self.answers.get(key), answer_rows, info
                )
        return questions

    @staticmethod
    def _question(measure_id, key, chosen, instruments, answer, answer_rows, repeat=None):
        return MergedQuestion(
            measure_id,
            chosen,
            instruments,
            section_name(chosen),
            answer,
            _answer_rows(answer, answer_rows),
            key=key,
            repeat=repeat,
        )

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
        if question.repeat is None:
            return position, instrument.order or 0, instrument.pk, 0, 0, 0
        # Copies sit where their group's first instrument sits, copy-major.
        anchor_order, anchor_pk = self._group_anchor_key[question.repeat.group_id]
        return (
            position,
            anchor_order,
            anchor_pk,
            question.repeat.index,
            instrument.order or 0,
            instrument.pk,
        )

    def _mark_first(self):
        """``repeat.first`` on each copy's first question in display order (render the heading)."""
        seen = set()
        for section in self.sections:
            for question in section.questions:
                if question.repeat is None:
                    continue
                copy = (question.repeat.group_id, question.repeat.index)
                if copy not in seen:
                    seen.add(copy)
                    question.repeat = replace(question.repeat, first=True)

    def _follow_parents(self, items) -> list:
        """A question gated on another request's question in this section sits right after it;
        a request's own order already places its dependants (Steven, 2026-10-08). Copies of a
        repeat group keep their place: they never move and never pull a question after them."""
        plain = [q for q in items if q.repeat is None]
        here = {q.key: q for q in plain}
        children = self._children()
        parent_of = {}
        for question in plain:
            for child in children.get(question.measure_id, ()):
                parent_of.setdefault(child, question.key)  # the earliest parent wins
        movers = set()
        grown = True
        while grown:  # to a fixed point: a child may sort before its moved parent
            grown = False
            for question in plain:
                if question.key in movers:
                    continue
                parent = here.get(parent_of.get(question.key))
                if parent is None:
                    continue
                crosses = (
                    parent.instrument.collection_request_id
                    != question.instrument.collection_request_id
                )
                if crosses or parent.key in movers:  # a moved parent takes its chain along
                    movers.add(question.key)
                    grown = True
        if not movers:
            return items
        placed, seen = [], set()

        def place(question):
            if question.key in seen:
                return
            seen.add(question.key)
            placed.append(question)
            for child in plain:
                if child.key in movers and parent_of[child.key] == question.key:
                    place(child)

        for question in items:
            if question.key not in movers:
                place(question)
        placed.extend(q for q in items if q.key not in seen)  # cycles: keep every question
        return placed

    def owner(self, key):
        """The instrument question ``key`` shows (a copy shows its measure's owner)."""
        return self.questions[key].instrument

    def evaluate(self, keys=None, *, measures=None) -> dict:
        """question key -> True if any request's instrument is allowed; None if none could say.

        A copy is evaluated inside its ``copy_scope``: gates in its group read that copy's
        answers, ``bound:`` reads its binding. ``measures`` is the pre-key name of ``keys``.
        A snapshot: answers are as of when the merge was built. Rebuild with merge_requests
        after writing inputs.
        """
        if keys is None:
            keys = measures
        keys = list(self.questions) if keys is None else keys
        with read_pass(index=self.index):
            return {key: self._visible(self.questions[key]) for key in keys}

    def _allowed(self, collector, instrument):
        if self.index is not None:
            return collector.is_instrument_allowed(instrument)
        with read_pass(index=self._indexes[instrument.collection_request_id]):
            return collector.is_instrument_allowed(instrument)

    def _visible(self, question):
        if question.repeat is None:
            return self._any_allowed(question)
        info = question.repeat
        with copy_scope(CurrentCopy(info.group_id, info.group_slug, info.index, info.binding)):
            return self._any_allowed(question)

    def _any_allowed(self, question):
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
                str(i.pk): measure_id
                for measure_id, instruments in self._entries.items()
                for i in instruments
            }
            children = defaultdict(set)
            for measure_id, instruments in self._entries.items():
                for instrument in instruments:
                    for condition in instrument.conditions.all():
                        kind, _, source = condition.data_getter.partition(":")
                        if kind == "instrument":
                            children[measure_of_pk.get(source, source)].add(measure_id)
            self._children_map = children
        return self._children_map

    def progress(self, visibility) -> dict:
        """Counts over question keys: each live copy of a repeat group counts as a question."""
        keys = ("total", "answered", "visible", "required_total", "required_answered")
        progress = dict.fromkeys(keys, 0)
        for question in self.questions.values():
            shown = visibility.get(question.key) is not False  # unknown still counts
            required = bool(question.is_required) and shown  # as the payload's is_required
            progress["total"] += 1
            progress["visible"] += bool(visibility.get(question.key))
            progress["required_total"] += required
            if question.answer is not None:
                progress["answered"] += 1
                progress["required_answered"] += required
        return progress
