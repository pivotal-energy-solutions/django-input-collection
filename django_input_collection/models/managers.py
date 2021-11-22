# -*- coding: utf-8 -*-
from django.db.models.query import QuerySet
from django.db.models import Q, Max, Count, OuterRef, Subquery

__all__ = ["CollectedInputQuerySet", "UserLatestCollectedInputQuerySet"]


class CollectionInstrumentQuerySet(QuerySet):
    """Filter operations for CollectionInstrument."""

    def filter_for_condition_resolver(self, name, sep=":"):
        if name == "*":
            return self.filter(conditions__isnull=False)
        return self.filter(conditions__data_getter__startswith=name + sep)

    def order_by_num_conditions(self):
        """Convenience method for ordering parent instruments before child instruments."""
        return self.annotate(Count("conditions")).order_by("conditions__count")


class CollectedInputQuerySet(QuerySet):
    """Provides a clear hook for doing special operations with a context."""

    def filter_for_context(self, **context):
        return self.filter(**context)


class UserLatestCollectedInputQuerySet(CollectedInputQuerySet):
    """
    Assumes a runtime context with  a ``user`` reference will always be provided, used to filter for
    only that user's most recent instances per CollectionInstrument.
    """

    def filter_for_context(self, user=None, **context):
        if user is not None:  # Allows an explicit None to avoid user references
            context["user"] = user

        queryset = super(UserLatestCollectedInputQuerySet, self).filter_for_context(**context)

        # Subquery for latest id per unique 'instrument' fk reference
        # This is kind of like what a Window() function would do for us, except we're not interested
        # in annotating ALL inputs, only plucking out the subset that apply.
        recent_inputs = (
            self.filter(instrument=OuterRef("instrument"))
            .order_by("-date_created")
            .values("id")[:1]
        )
        queryset = self.filter(id=Subquery(recent_inputs))
        return queryset
