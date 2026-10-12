"""repeat.py: repeat-group question keys, copy labels, and the copy being evaluated."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

__all__ = [
    "KEY_SEPARATOR",
    "Copy",
    "CurrentCopy",
    "question_key",
    "parse_key",
    "render_label",
    "current_copy",
    "copy_scope",
    "read_context",
    "scoped_index",
    "set_repeat_anchor",
    "repeat_anchor",
]

KEY_SEPARATOR = "#"  # not in the MEASURE URL regex [\w-]: a key is never mistaken for a measure
WRITE_CONTEXT_KEY = "repeat_index"  # a write collector's copy, in its context
_ANCHOR_ATTR = "_repeat_anchor"


@dataclass(frozen=True)
class Copy:
    """One live copy of a group, as ``resolve_repeat`` returns it."""

    index: int  # 1-based
    label: str
    binding: object | None = None  # model instance for simulation-set copies


@dataclass(frozen=True)
class CurrentCopy:
    """The copy whose conditions are being evaluated.

    Groups match by ``group_slug``, not pk: a merge holds one cloned request per program, each
    with its own RepeatGroup row for the same group.
    """

    group_id: int  # RepeatGroup.pk
    group_slug: str
    index: int
    binding: object | None = None


_current_copy: ContextVar = ContextVar("repeat_current_copy", default=None)


def question_key(measure_id: str, index: int | None) -> str:
    """``measure_id`` for an ordinary question, ``measure_id#n`` for copy n."""
    return measure_id if index is None else f"{measure_id}{KEY_SEPARATOR}{index}"


def parse_key(key: str) -> tuple[str, int | None]:
    """Inverse of ``question_key``; raises ValueError on "m#0", "m#x", "#2", ""."""
    measure_id, separator, index = key.partition(KEY_SEPARATOR)
    if not measure_id:
        raise ValueError(f"Question key {key!r} has no measure")
    if not separator:
        return measure_id, None
    if not index.isdigit() or int(index) < 1:
        raise ValueError(f"Question key {key!r} needs a copy number of 1 or more")
    return measure_id, int(index)


def render_label(template: str, *, n: int, label: str = "", group_name: str = "") -> str:
    """A copy heading: ``{n}`` is the ordinal, ``{label}`` the bound object's label.

    An empty template is ``"{group name} {n}"``. Other braces are left as written.
    """
    if not template:
        return f"{group_name} {n}".strip()
    return template.replace("{n}", str(n)).replace("{label}", label)


def current_copy() -> CurrentCopy | None:
    """The copy being evaluated, or None outside a copy."""
    return _current_copy.get()


@contextmanager
def copy_scope(copy: CurrentCopy | None):
    """Evaluate conditions inside ``copy`` (None: outside any copy) for the block."""
    token = _current_copy.set(copy)
    try:
        yield
    finally:
        _current_copy.reset(token)


def read_context(context: dict) -> dict:
    """A collector context for reading: without the write copy (``repeat_index``).

    The copy a gate reads is decided by ``current_copy()`` per gating instrument, never by the
    collector's write context.
    """
    return {key: value for key, value in context.items() if key != WRITE_CONTEXT_KEY}


def scoped_index(instrument, copy: CurrentCopy | None) -> int | None:
    """The copy index ``instrument``'s rows are read at: ``copy.index`` when its group has the
    copy's slug, else None (only unrepeated rows)."""
    if copy is None:
        return None
    group = getattr(instrument, "repeat_group", None)
    if group is not None and group.slug == copy.group_slug:
        return copy.index
    return None


def set_repeat_anchor(group, instrument) -> None:
    """Remember ``group``'s first instrument (callers that already loaded them, e.g. the merge)."""
    setattr(group, _ANCHOR_ATTR, instrument)


def repeat_anchor(group):
    """The group's first instrument by (order, pk): what its group conditions resolve against."""
    anchor = getattr(group, _ANCHOR_ATTR, None)
    if anchor is None:
        anchor = group.instruments.order_by("order", "pk").first()
        set_repeat_anchor(group, anchor)
    return anchor
