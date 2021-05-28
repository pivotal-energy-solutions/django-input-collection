from django.utils.translation import gettext_lazy as _

from .base import InputMethod


__all__ = ["CharMethod", "IntegerMethod", "FloatMethod"]


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
