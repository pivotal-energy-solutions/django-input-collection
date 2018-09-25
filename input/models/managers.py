from django.db.models.query import QuerySet
from django.db.models import Q, Max, OuterRef, Subquery



class ContextualMixin(object):
    """ Provides a clear hook for doing special operations with a context. """
    def filter_for_context(self, **context):
        return self.filter(**context)


class CollectedInputQuerySet(ContextualMixin, QuerySet):
    pass


class UserLatestCollectedInputQuerySet(CollectedInputQuerySet):
    """
    Assumes a runtime context with  a ``user`` reference will always be provided, used to filter for
    only that user's most recent instances per CollectionInstrument.
    """

    def filter_for_context(self, user, **context):
        if user is not None:  # Allows an explicit None to avoid user references
            context['user'] = user

        queryset = super(UserLatestCollectedInputQuerySet, self).filter_for_context(**context)

        # Subquery for latest id per unique 'instrument' fk reference
        # This is kind of like what a Window() function would do for us, except we're not interested
        # in annotating ALL inputs, only plucking out the subset that apply.
        recent_inputs = self.filter(instrument=OuterRef('instrument')) \
                            .order_by('-date_created') \
                            .values('id')[:1]
        queryset = self.filter(id=Subquery(recent_inputs))
        return queryset
