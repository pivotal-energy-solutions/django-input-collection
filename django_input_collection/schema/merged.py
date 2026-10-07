"""merged.py: the checklist response for a MergedChecklist (ChecklistConsumerMixin's shape, merged)."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from ..collection.merged_checklist import GENERAL


def response_flags(bound) -> dict:
    """Flags on a bound response; swapped bound models with ``get_flags()`` supply them."""
    get_flags = getattr(bound, "get_flags", None)
    return (get_flags() or {}) if callable(get_flags) else {}


def _question(consumer, question, collectors, visible, by_measure, answer_payload, extras):
    instrument = question.instrument  # the owner's
    policy = instrument.response_policy
    collector = collectors[instrument.collection_request_id]
    payload = {
        "id": instrument.pk,
        "measure_id": question.measure_id,
        "collection_request": instrument.collection_request_id,
        "collection_requests": [i.collection_request_id for i in question.instruments],
        "text": instrument.text or "",
        "description": instrument.description or "",
        "help_text": instrument.help or "",
        "type": instrument.type_id or "open",
        "order": instrument.order or 0,
        "is_required": policy and policy.required,  # as the mixin: None without a policy
        "is_visible": visible,
        "constraints": consumer._get_instrument_constraints(collector, instrument),
        "responses": consumer._get_responses_with_flags(instrument),  # bound rows prefetched
        "conditions": consumer._get_conditions(instrument, by_measure),
        "answer": answer_payload(question.answer) if question.answer is not None else None,
        # A multi-value answer whole: what the rater sees is what conditions evaluate.
        "answers": [answer_payload(row) for row in question.answers],
    }
    if extras:
        payload.update(extras(question, payload))
    return payload


def consumer_payload(
    consumer, merged, *, collectors, visibility=None, question_extras=None, answer_payload=None
) -> dict:
    """``merged_checklist_payload`` built with ``consumer``'s (a ChecklistConsumerMixin) per-question
    overrides: ``_get_responses_with_flags`` (so ``_get_bound_response_flags`` /
    ``_get_response_flags``), ``_get_conditions`` / ``_serialize_condition``,
    ``_get_instrument_constraints``, ``_slugify`` and ``_serialize_answer``. Visibility is the
    merge's (shown if any request shows it); ``_get_instrument_visibility`` is not called.
    """
    visibility = merged.evaluate() if visibility is None else visibility
    answer_payload = answer_payload or consumer._serialize_answer
    by_measure = {measure_id: q.instrument for measure_id, q in merged.questions.items()}
    sections = []
    for section in merged.sections:
        questions = [
            _question(
                consumer,
                question,
                collectors,
                visibility.get(question.measure_id),
                by_measure,
                answer_payload,
                question_extras,
            )
            for question in section.questions
        ]
        group = None if section.name == GENERAL else section.questions[0].instrument.group
        sections.append(consumer._section_data(group, questions))
    sections.sort(key=lambda s: s["order"])  # as the mixin: stable, General (-1) first
    return {
        "requests": [request.pk for request in merged.requests],
        "sections": sections,
        "progress": merged.progress(visibility),
    }


def merged_checklist_payload(
    merged,
    *,
    collectors,
    visibility=None,
    question_extras=None,
    answer_payload=None,
    consumer=None,
) -> dict:
    """``merged`` in ChecklistConsumerMixin's checklist shape: the same section, question and
    answer keys and values, plus per question ``collection_request`` (the owner's),
    ``collection_requests`` (every asking request) and ``answers`` (every row of the answering
    instrument, oldest first); top level ``requests``, ``sections``, ``progress`` (no
    ``id``/``name``/``description``: no single request names a merge).

    ``visibility`` (default ``merged.evaluate()``) maps measure_id -> visible.
    ``question_extras(question, payload) -> dict`` adds keys per question; ``answer_payload(row)``
    replaces the mixin's ``_serialize_answer``. Reads nothing the merge didn't prefetch.
    ``answers`` come from the merge's ``inputs``; when conditions read a narrower
    ``condition_inputs``, "answers = what conditions read" holds only where the rows agree.

    ``consumer`` (a ChecklistConsumerMixin subclass or instance, e.g. the viewset class) applies
    its overrides as ``consumer_payload`` does, so a caller outside a view gets the view's shape.
    Default: the plain mixin.
    """
    from .mixins import ChecklistConsumerMixin

    consumer = ChecklistConsumerMixin if consumer is None else consumer
    return consumer_payload(
        consumer() if isinstance(consumer, type) else consumer,
        merged,
        collectors=collectors,
        visibility=visibility,
        question_extras=question_extras,
        answer_payload=answer_payload,
    )
