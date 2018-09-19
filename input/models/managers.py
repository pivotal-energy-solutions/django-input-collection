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

    # def as_manager(cls, context):
    #     """ Adds required ``context`` arg for initialization. """
    #     manager = super(ContextualQuerySet, cls).as_manager()
    #     manager.context = context.copy()
    #     return manager
    # as_manager.queryset_only = True
    # as_manager = classmethod(as_manager)


class UserLatestCollectedInputQuerySet(ContextualCollectedInputQuerySet):
    """
    Assumes a runtime context with  a ``user`` reference will always be provided, used to filter for
    only that user's most recent instances per CollectionInstrument.
    """
    latest = Max('date_created')

    def get_context_query(self, user, **extra):
        """
        Uses a required ``user`` runtime context kwarg, used for finding only the most recent
        instances per CollectionInstrument.
        """
        extra['user'] = user
        return super(LatestCollectedInputQuerySet, self).get_context_query(**extra)

    def filter_for_context(self, user, **extra):
        
        extra['user'] = user
        queryset = super(UserLatestCollectedInputQuerySet, self).filter_for_context(**extra)
        # queryset = queryset.aggregate(latest)
        return queryset
