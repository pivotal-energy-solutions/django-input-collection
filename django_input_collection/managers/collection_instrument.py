# -*- coding: utf-8 -*-
from django.db.models import QuerySet, Count


class CollectionInstrumentQuerySet(QuerySet):
    """Filter operations for CollectionInstrument."""

    def filter_for_condition_resolver(self, name, sep=":"):
        if name == "*":
            return self.filter(conditions__isnull=False)
        return self.filter(conditions__data_getter__startswith=name + sep)

    def order_by_num_conditions(self):
        """Convenience method for ordering parent instruments before child instruments."""
        return self.annotate(Count("conditions")).order_by("conditions__count")
