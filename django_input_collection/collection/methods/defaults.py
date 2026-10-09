from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .base import InputMethod


__all__ = [
    "CharMethod",
    "IntegerMethod",
    "FloatMethod",
    "EvidenceMethod",
    "EVIDENCE_TYPE",
    "EVIDENCE_INPUT",
    "EVIDENCE_KINDS",
]

EVIDENCE_TYPE = "evidence"
EVIDENCE_INPUT = "Uploaded"  # what an evidence answer stores; its files are the answer
EVIDENCE_KINDS = ("photo", "video", "document")


class CharMethod(InputMethod):
    cleaner = str  # FIXME: Definitely an encoding bug waiting to happen


class IntegerMethod(InputMethod):
    cleaner = int
    errors = {
        Exception: _("Please enter a valid integer."),
    }


class FloatMethod(InputMethod):
    cleaner = float
    errors = {
        Exception: _("Please enter a valid float."),
    }


class EvidenceMethod(InputMethod):
    """An evidence question: no value to type or choose, only the marker that files arrived."""

    def clean_input(self, data):
        # Base clean_input funnels every exception through a broken error lookup (KeyError)
        return self.clean(data)

    def clean(self, data):
        if data != EVIDENCE_INPUT:
            raise ValidationError("An evidence question is answered by uploading a file.")
        return data
