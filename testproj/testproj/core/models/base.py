from django.db import models


# Simplest example of all-in-one collection
class Survey(models.Model):
    title = models.CharField(max_length=50)
    start_time = models.DateTimeField(auto_now=True)
    end_time = models.DateTimeField(blank=True, null=True)

    # CollectionRequest is guaranteed to be unique to this Survey
    collection_request = models.OneToOneField('input.CollectionRequest')


# Multi-stage collection example driven by some kind of business logic for the segmentation
class PoliticalRally(models.Model):
    """
    Tracks multiple data-gathering efforts on a single logical model instance.  Note that the
    CollectionRequests are always single-use, so the ``colleciton_requests`` ManyToManyField should
    always include a ``through`` model where uniqueness of the request is ensured.
    """
    title = models.CharField(max_length=50)
    location = models.CharField(max_length=50)
    time = models.DateTimeField(auto_now_add=True)

    # Multiple CollectionRequests allowed, but tracked via a ``through`` model to ensure we can't
    # accidentally associate the same CollectionRequest to more than one PoliticalRally.
    collection_requests = models.ManyToManyField('input.CollectionRequest', through='RallyPoll')


class RallyPoll(models.Model):
    """
    The ``through`` model which tracks one CollectionRequest for a given PoliticalRally
    """
    # The rally that is offering more than one RallyPoll
    rally = models.ForeignKey('PoliticalRally')

    # Associate uniquely to a CollectionRequest.  Both OneToOne and ForeignKey(unique=True) are
    # allowable.
    collection_request = models.OneToOneField('input.CollectionRequest')

    # Arbitrary other constraints for the business logic that may justify having multiple
    # CollectionRequests in play on a single PoliticalRally.
    start_time = models.DateTimeField(auto_now=True)
    end_time = models.DateTimeField(blank=True, null=True)
