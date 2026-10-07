"""merged.py: the checklist response for a MergedChecklist (ChecklistConsumerMixin's keys, merged)."""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from django.utils.text import slugify


def response_flags(bound) -> dict:
    """Flags on a bound response; swapped bound models with ``get_flags()`` supply them."""
    get_flags = getattr(bound, "get_flags", None)
    return (get_flags() or {}) if callable(get_flags) else {}


def _responses(instrument):
    bound_rows = list(instrument.bound_suggested_responses.all())  # prefetched by the merge
    if not bound_rows:
        return None
    found = []
    for bound in bound_rows:
        item = {"value": bound.suggested_response.data}
        flags = response_flags(bound)
        if flags:
            item["flags"] = flags
        found.append(item)
    return found


def _conditions(instrument):
    """The mixin's condition keys, plus the group's requirement and cases (all prefetched)."""
    found = []
    for condition in instrument.conditions.all():
        if not condition.data_getter:
            continue
        kind, colon, source = condition.data_getter.partition(":")
        if not colon:  # as the mixin: no prefix means an instrument
            kind, source = "instrument", kind
        group = condition.condition_group
        found.append(
            {
                "type": kind,
                "source": source,
                "match_type": "match",  # as the mixin: conditions carry no match type of their own
                "values": [],
                "requirement_type": group.requirement_type,
                "cases": [
                    {"match_type": case.match_type, "match_data": case.match_data}
                    for case in group.cases.all()
                ],
            }
        )
    return found


def _constraints(collector, instrument):
    try:
        method = collector.get_method(instrument)
        return method.get_constraints() if hasattr(method, "get_constraints") else None
    except Exception:  # as the mixin: no method, no constraints
        return None


def default_answer_payload(row) -> dict:
    """The mixin's answer keys (``ChecklistConsumerMixin._serialize_answer``)."""
    return {
        "id": row.pk,
        "data": row.data,
        "user_id": row.user_id,
        "user_role": getattr(row, "user_role", None),
        "date_created": row.date_created.isoformat() if row.date_created else None,
        "date_modified": row.date_modified.isoformat() if row.date_modified else None,
    }


def _question(question, collectors, visible, answer_payload, extras):
    instrument = question.instrument  # the owner's
    policy = instrument.response_policy
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
        "is_required": bool(policy and policy.required),
        "is_visible": visible,
        "constraints": _constraints(collectors[instrument.collection_request_id], instrument),
        "responses": _responses(instrument),
        "conditions": _conditions(instrument),
        "answer": answer_payload(question.answer) if question.answer is not None else None,
        # A multi-value answer whole: what the rater sees is what conditions evaluate.
        "answers": [answer_payload(row) for row in question.answers],
    }
    if extras:
        payload.update(extras(question, payload))
    return payload


def merged_checklist_payload(
    merged, *, collectors, visibility=None, question_extras=None, answer_payload=None
) -> dict:
    """``merged`` as ChecklistConsumerMixin's checklist: same question and answer keys, plus
    ``collection_request`` (the owner's), ``collection_requests`` (every asking request) and
    ``answers``; top level ``requests``, ``sections``, ``progress``.

    ``visibility`` (default ``merged.evaluate()``) maps measure_id -> visible.
    ``question_extras(question, payload) -> dict`` adds keys per question; ``answer_payload(row)``
    replaces ``default_answer_payload``. Reads nothing the merge didn't prefetch.
    """
    visibility = merged.evaluate() if visibility is None else visibility
    answer_payload = answer_payload or default_answer_payload
    sections = [
        {
            "name": section.name,
            "slug": slugify(section.name) or "section",
            "description": "",
            "order": section.order,
            "questions": [
                _question(
                    question,
                    collectors,
                    visibility.get(question.measure_id),
                    answer_payload,
                    question_extras,
                )
                for question in section.questions
            ],
        }
        for section in merged.sections
    ]
    return {
        "requests": [request.pk for request in merged.requests],
        "sections": sections,
        "progress": merged.progress(visibility),
    }
