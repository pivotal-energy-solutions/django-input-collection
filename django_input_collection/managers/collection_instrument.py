from django.db.models import QuerySet, Count

# Everything test_conditions() walks: conditions -> group -> (cases, child groups -> cases).
# Deeper nesting is unsupported (see ConditionGroup.child_groups) and falls back to queries.
CONDITION_PREFETCH = (
    "conditions__condition_group__cases",
    "conditions__condition_group__child_groups__cases",
    "conditions__condition_group__child_groups__child_groups",
)


class CollectionInstrumentQuerySet(QuerySet):
    """Filter operations for CollectionInstrument."""

    def with_conditions(self):
        """Prefetch the condition tree so test_conditions() runs without per-instrument queries."""
        return self.prefetch_related(*CONDITION_PREFETCH)

    def filter_for_condition_resolver(self, name, sep=":"):
        if name == "*":
            return self.filter(conditions__isnull=False)
        return self.filter(conditions__data_getter__startswith=name + sep)

    def order_by_num_conditions(self):
        """Convenience method for ordering parent instruments before child instruments."""
        return self.annotate(Count("conditions")).order_by("conditions__count")
