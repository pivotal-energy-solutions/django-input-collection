from django.db.models.query import QuerySet
from django.db.models import Q, Max, OuterRef, Subquery


class ContextualMixin(object):
    context = None

    def get_queryset(self):
        """ Forces filter_for_context() for all querysets. """
        return super(ContextualQuerySet, self).get_queryset().filter_for_context()

    def set_context(self, context):
        self.context = context.copy()

    def get_context(self, **extra):
        """ Returns a copy of ``self.context`` merged with extra runtime kwargs. """
        return dict(self.context or {}, **extra)

    def get_context_query(self, **extra):
        """ Returns a Q() object from ``self.get_context()``. """
        context = self.get_context(**extra)
        return Q(**context)

    def filter_for_context(self, **extra):
        """ Applies the Q() object returned by ``get_context_query()``. """
        q = self.get_context_query(**extra)
        return self.filter(q)


class CollectedInputQuerySet(QuerySet):
    pass


class ContextualCollectedInputQuerySet(ContextualMixin, CollectedInputQuerySet):
    pass


class UserLatestCollectedInputQuerySet(ContextualCollectedInputQuerySet):
    """
    Assumes a runtime context with  a ``user`` reference will always be provided, used to filter for
    only that user's most recent instances per CollectionInstrument.
    """

    def get_context_query(self, user, **extra):
        """
        Uses a required ``user`` runtime context kwarg, used for finding only the most recent
        instances per CollectionInstrument.
        """
        if user is not None:  # Allows an explicit None to avoid user references
            extra['user'] = user
        return super(UserLatestCollectedInputQuerySet, self).get_context_query(**extra)

    def filter_for_context(self, user, **extra):
        if user is not None:  # Allows an explicit None to avoid user references
            extra['user'] = user

        queryset = super(UserLatestCollectedInputQuerySet, self).filter_for_context(**extra)

        # Subquery for latest id per unique 'instrument' fk reference
        # This is kind of like what a Window() function would do for us, except we're not interested
        # in annotating ALL inputs, only plucking out the subset that apply.
        recent_inputs = self.filter(instrument=OuterRef('instrument')) \
                            .order_by('-date_created') \
                            .values('id')[:1]
        queryset = self.filter(id=Subquery(recent_inputs))
        return queryset
