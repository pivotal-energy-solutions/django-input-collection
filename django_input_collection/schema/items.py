"""items.py: walk a checklist schema's questions with repeat items flattened in place."""

__author__ = "Steven Klass"
__date__ = "10/11/26 09:00 AM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from collections.abc import Iterator


def iter_questions(sections) -> Iterator[tuple[dict, dict | None]]:
    """(question, its repeat dict or None) for every question, in schema order.

    Works on raw, validated and exported schemas alike: a section's ``questions`` holds question
    dicts and ``{"repeat": {..., "questions": [...]}}`` items.
    """
    for section in sections or ():
        for item in section.get("questions", []):
            repeat = item.get("repeat")
            if repeat is None:
                yield item, None
            else:
                for question in repeat.get("questions", []):
                    yield question, repeat


def iter_rules(conditions) -> Iterator[dict]:
    """Every rule of ``conditions``: simple ones as given, group ones' ``rules`` flattened."""
    for condition in conditions or ():
        if condition.get("rules"):
            yield from condition["rules"]
        else:
            yield condition
