from django.db import models

import swapper

__all__ = ['CollectionRequest', 'CollectionGroup', 'CollectionInstrument', 'CollectedInput',
           'get_input_model']


class CollectionGroup(models.Model):
    """
    A canonical grouping label for deployed questions to relate to, for business-logic purposes.
    """
    id = models.CharField(max_length=100, primary_key=True)

    def __str__(self):
        return self.id


class CollectionRequest(models.Model):
    """
    A contextual grouping that calls for some number of questions to be put forward for a data
    collection step.
    """

    # Also available:
    #
    # self.instruments.all()
    # self.collectedinput_set.all()

    def __str__(self):
        return str(self.id)


class CollectionInstrument(models.Model):
    """
    The presentation of a Measure with all relevant contextual information to scope it to a specific
    data-gathering effort, regardless of any commonalities with other gathering efforts (such as
    phrasing, etc).
    """

    collection_request = models.ForeignKey('CollectionRequest', related_name='instruments', on_delete=models.CASCADE)
    measure = models.ForeignKey('Measure', on_delete=models.CASCADE)
    group = models.ForeignKey('CollectionGroup', on_delete=models.CASCADE)

    text = models.TextField()

    # Also available:
    #
    # self.collectedinput_set.all()

    def __str__(self):
        return self.text


class AbstractCollectedInput(models.Model):
    """
    Abstract definition of a single point of data collected for a given Measure, related to the
    CollectionInstrument used to gather it. Many CollectedInputs are gathered in a
    CollectionRequest.

    A ``data`` field must be supplied by a concrete sublcass.
    """
    collection_request = models.ForeignKey('CollectionRequest', on_delete=models.CASCADE)
    instrument = models.ForeignKey('CollectionInstrument', on_delete=models.CASCADE)
    group = models.ForeignKey('CollectionGroup', on_delete=models.CASCADE)

    class Meta:
        abstract = True


MODEL_SWAP_SETTING = swapper.swappable_setting('input', 'CollectedInput')

class CollectedInput(AbstractCollectedInput):
    """
    A single point of data collected for a given Measure, related to the CollectionInstrument used
    to gather it.  Many CollectedInputs are gathered in a CollectionRequest.
    """

    data = models.CharField(max_length=512)

    class Meta:
        swappable = MODEL_SWAP_SETTING  # 'INPUT_COLLECTEDINPUT_MODEL'


def get_input_model():
    return swapper.load_model('input', 'CollectedInput')
