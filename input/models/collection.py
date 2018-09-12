from django.db import models

import swapper

from .. import collection
from .utils import DatesMixin

__all__ = ['CollectionRequest', 'CollectionGroup', 'CollectionInstrument', 'AbstractCollectedInput',
           'CollectedInput']


class CollectionGroup(DatesMixin, models.Model):
    """
    A canonical grouping label for deployed questions to relate to, for business-logic purposes.
    """
    id = models.CharField(max_length=100, primary_key=True)

    def __str__(self):
        return self.id


class CollectionRequest(DatesMixin, models.Model):
    """
    A contextual grouping that calls for some number of questions to be put forward for a data
    collection step.
    """

    # Also available:
    #
    # self.instruments.all()
    # self.collectedinput_set.all()  [default, changes if swapped]

    def __str__(self):
        return str(self.id)


class CollectionInstrument(DatesMixin, models.Model):
    """
    The presentation of a Measure with all relevant contextual information to scope it to a specific
    data-gathering effort, regardless of any commonalities with other gathering efforts (such as
    phrasing, etc).
    """

    collection_request = models.ForeignKey('CollectionRequest', related_name='instruments', on_delete=models.CASCADE)
    measure = models.ForeignKey('Measure', on_delete=models.CASCADE)
    group = models.ForeignKey('CollectionGroup', on_delete=models.CASCADE)

    text = models.TextField()

    response_policy = models.ForeignKey('ResponsePolicy', on_delete=models.CASCADE)
    suggested_responses = models.ManyToManyField('SuggestedResponse')

    # Also available:
    #
    # self.suggestedresponse_set.all()
    # self.collectedinput_set.all()  [default, changes if swapped]

    def __str__(self):
        return self.text

    def receive(self, data):
        return collection.store(self, data)


class ResponsePolicy(DatesMixin, models.Model):
    """
    Flags that define an archetypical way to respond to a category of CollectionInstruments.
    CollectionInstruments may point to a common ResponsePolicy, or define separate instances for
    finer control over a specific CollectionInstrument's policy flags.
    """
    # Internal references
    nickname = models.CharField(max_length=100, null=True)

    # Flags for related CollectionInstrument(s)
    # NOTE: 'multiple' should be treated like a hint suggesting that a CollectedInput for an
    # instrument will be serialized to fit into the ``input.data`` field, and that it must be
    # deserialized later.
    restrict = models.BooleanField()  # must supply answer matching a SuggestedResponse
    multiple = models.BooleanField()  # allows multiple selections

    def get_flags(self):
        return {
            'restrict': self.restrict,
            'multiple': self.multiple,
        }


class SuggestedResponse(DatesMixin, models.Model):
    """
    A pre-identified valid response for a CollectionInstrument.
    """
    data = models.CharField(max_length=512)

    # Also available:
    #
    # self.collectioninstrument_set.all()


class AbstractCollectedInput(DatesMixin, models.Model):
    """
    Abstract definition of a single point of data collected for a given Measure, related to the
    CollectionInstrument used to gather it. Many CollectedInputs are gathered in a
    CollectionRequest.

    A ``data`` field must be supplied by a concrete sublcass.
    """

    # Note that these fk references MUST include this app's label, since otherwise, anyone
    # inheriting from this abstract base will end up with ForeignKey references that appear local.
    collection_request = models.ForeignKey('input.CollectionRequest', on_delete=models.CASCADE)
    instrument = models.ForeignKey('input.CollectionInstrument', on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.data)


MODEL_SWAP_SETTING = swapper.swappable_setting('input', 'CollectedInput')

class CollectedInput(AbstractCollectedInput):
    """
    A single point of data collected for a given Measure, related to the CollectionInstrument used
    to gather it.  Many CollectedInputs are gathered in a CollectionRequest.
    """

    data = models.CharField(max_length=512)

    class Meta:
        swappable = MODEL_SWAP_SETTING  # 'INPUT_COLLECTEDINPUT_MODEL'
