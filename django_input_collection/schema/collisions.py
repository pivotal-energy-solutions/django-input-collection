"""collisions.py: a measure shared across collection requests must be the same question.

The library compares; the caller decides which pairs to skip and how serious a mismatch is.
"""

__author__ = "Steven Klass"
__date__ = "10/07/26 04:00 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from dataclasses import dataclass, field

from .registry import BoundResponseRegistry

COLLISION_FIELDS = ("type", "responses", "response_flags", "required", "text", "provides_for")


@dataclass(frozen=True)
class MeasureSignature:
    type: str
    responses: tuple
    response_flags: tuple  # ((response value, ((flag, value), ...)), ...), truthy flags only
    required: bool
    text: str
    provides_for: tuple
    description: str = ""  # carried for reports, never compared
    help: str = ""


def normalize_flags(flags_by_response: dict) -> tuple:
    """Order-insensitive flags coerced to bool; falsy flags and flagless responses drop out."""
    found = []
    for value, flags in (flags_by_response or {}).items():
        items = tuple(sorted((str(k), True) for k, v in (flags or {}).items() if v))
        if items:
            found.append((str(value), items))
    return tuple(sorted(found))


def provides_for(context) -> tuple:
    """``provides_for`` as a sorted tuple; None, missing and [] are all ().

    A bare string is malformed (consumers would iterate its characters), so it is kept raw and
    surfaces as a difference against any proper list.
    """
    value = context.get("provides_for") if isinstance(context, dict) else None
    if not value:
        return ()
    if isinstance(value, str):
        return value
    return tuple(sorted(str(v) for v in value))


def _schema_flags(question: dict, responses: tuple) -> tuple:
    """Flags as the builder stores them: none without a handler, only for listed responses."""
    if not BoundResponseRegistry.has_handler():
        return ()
    flags = question.get("response_flags") or {}
    return normalize_flags({k: v for k, v in flags.items() if str(k) in responses})


def _schema_type(question: dict) -> str:
    from .builder import CollectionRequestBuilder

    return CollectionRequestBuilder.TYPE_MAP.get(question.get("type", "open"), "open")


def signatures_from_schema(schema: dict) -> dict:
    """Signatures as ``CollectionRequestBuilder.build`` would store them; no queries."""
    response_sets = schema.get("response_sets", {})
    found = {}
    for section in schema.get("sections", []):
        for q in section.get("questions", []):
            responses = q.get("responses") or response_sets.get(q.get("response_set"), [])
            responses = tuple(str(r) for r in responses)
            found[q["measure_id"]] = MeasureSignature(
                type=_schema_type(q),
                responses=responses,
                response_flags=_schema_flags(q, responses),
                required=bool(q.get("required", True)),
                text=q.get("text") or "",
                provides_for=provides_for(q.get("context")),
                description=q.get("description") or "",
                help=q.get("help_text") or "",
            )
    return found


def _instrument_flags(instrument, bound_rows) -> dict:
    """Bound ``get_flags()`` (prefetched, no queries); else the registered handler's export,
    which may cost a query per instrument."""
    from .merged import response_flags

    if bound_rows and not callable(getattr(bound_rows[0], "get_flags", None)):
        return BoundResponseRegistry.export(instrument)  # {} without a handler
    return {b.suggested_response.data: response_flags(b) for b in bound_rows}


def signature_from_instrument(instrument) -> MeasureSignature:
    """Reads prefetched bound responses; see ``signatures_for_request``."""
    bound_rows = sorted(instrument.bound_suggested_responses.all(), key=lambda b: b.pk)
    policy = instrument.response_policy
    return MeasureSignature(
        type=instrument.type_id or "open",
        responses=tuple(b.suggested_response.data for b in bound_rows),
        response_flags=normalize_flags(_instrument_flags(instrument, bound_rows)),
        required=bool(policy and policy.required),
        text=instrument.text or "",
        provides_for=provides_for(instrument.context),
        description=instrument.description or "",
        help=instrument.help or "",
    )


def signatures_for_request(collection_request) -> dict:
    """Signatures of a stored request in a fixed number of queries when the bound model has
    ``get_flags()``; the registry-export fallback may add a query per instrument."""
    instruments = collection_request.collectioninstrument_set.select_related(
        "response_policy"
    ).prefetch_related("bound_suggested_responses__suggested_response")
    return {i.measure_id: signature_from_instrument(i) for i in instruments}


@dataclass(frozen=True)
class MeasureCollision:
    measure_id: str
    subject: object
    other: object
    differences: dict  # field -> (subject value, other value)

    def __str__(self):
        diffs = "; ".join(f"{k}: {a!r} vs {b!r}" for k, (a, b) in self.differences.items())
        return f"{self.measure_id}: {self.subject} vs {self.other}: {diffs}"


def differences(a: MeasureSignature, b: MeasureSignature) -> dict:
    return {
        name: (getattr(a, name), getattr(b, name))
        for name in COLLISION_FIELDS
        if getattr(a, name) != getattr(b, name)
    }


def find_measure_collisions(subject_key, subject, others, *, skip=None) -> list:
    """Every shared measure whose compared fields differ; ``skip(subject_key, other_key)`` opts out."""
    found = []
    for other_key, signatures in others.items():
        if other_key == subject_key or (skip and skip(subject_key, other_key)):
            continue
        for measure_id in sorted(set(subject) & set(signatures)):
            diff = differences(subject[measure_id], signatures[measure_id])
            if diff:
                found.append(MeasureCollision(measure_id, subject_key, other_key, diff))
    return found


class MeasureCollisionError(Exception):
    def __init__(self, collisions):
        self.collisions = list(collisions)
        super().__init__("Shared measures differ:\n" + "\n".join(map(str, self.collisions)))


@dataclass
class CollisionReport:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def raise_for_errors(self):
        if self.errors:
            raise MeasureCollisionError(self.errors)


def check_measure_collisions(subject_key, subject, others, *, severity, skip=None):
    """``severity(collision)`` returns "error", "warning" or None (ignored)."""
    report = CollisionReport()
    for collision in find_measure_collisions(subject_key, subject, others, skip=skip):
        level = severity(collision)
        if level == "error":
            report.errors.append(collision)
        elif level == "warning":
            report.warnings.append(collision)
    return report
