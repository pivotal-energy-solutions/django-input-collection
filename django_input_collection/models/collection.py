import operator

from django.db import models
from django.contrib.auth.models import AnonymousUser
from django.conf import settings

import swapper

from . import managers
from .base import DatesModel

__all__ = ['Measure', 'CollectionRequest', 'CollectionGroup', 'CollectionInstrumentType',
           'CollectionInstrument', 'ResponsePolicy', 'SuggestedResponse', 'AbstractCollectedInput',
           'CollectedInput', 'MODEL_SWAP_SETTING']


class Measure(DatesModel, models.Model):
    """
    A deployed question's underlying identity, regardless of phrasing or possible answer choices.
    Models that collect for a Measure use a ForeignKey pointing to the appropriate Measure.
    """
    id = models.CharField(max_length=100, primary_key=True)

    def __str__(self):
        return self.id


class CollectionGroup(DatesModel, models.Model):
    """
    A canonical grouping label for deployed questions to relate to, for business-logic purposes.
    """
    id = models.CharField(max_length=100, primary_key=True)

    def __str__(self):
        return self.id


class CollectionRequest(DatesModel, models.Model):
    """
    A contextual grouping that calls for some number of questions to be put forward for a data
    collection step.
    """

    # Global data integrity settings

    # Maximum inputs for a single user for a single Instrument.
    # NOTE: If the CollectedInput queryset's ``filter_for_context()`` returns fewer items in its
    # queryset than specified in this setting, it will be impossible for this setting to be enforced
    # at runtime.
    max_instrument_inputs_per_user = models.PositiveIntegerField(blank=True, null=True)

    # Maximum inputs across all users for a single Instrument.
    max_instrument_inputs = models.PositiveIntegerField(blank=True, null=True)

    # Also available:
    #
    # self.collectioninstrument_set.all()
    # self.collectedinput_set.all()

    def __str__(self):
        return str(self.id)

    def get_flags(self):
        return {
            'max_instrument_inputs_per_user': self.max_instrument_inputs_per_user,
            'max_instrument_inputs': self.max_instrument_inputs,
        }


class CollectionInstrumentType(DatesModel, models.Model):
    id = models.CharField(max_length=100, primary_key=True)

    def __str__(self):
        return self.id


class CollectionInstrument(DatesModel, models.Model):
    """
    The presentation of a Measure with all relevant contextual information to scope it to a specific
    data-gathering effort, regardless of any commonalities with other gathering efforts (such as
    phrasing, etc).
    """

    collection_request = models.ForeignKey('CollectionRequest', on_delete=models.CASCADE)
    measure = models.ForeignKey('Measure', on_delete=models.CASCADE)
    group = models.ForeignKey('CollectionGroup', on_delete=models.CASCADE)
    type = models.ForeignKey('CollectionInstrumentType', blank=True, null=True,
                             on_delete=models.SET_NULL)

    order = models.IntegerField(default=0)

    text = models.TextField()
    description = models.TextField(blank=True)  # short text, always displayed
    help = models.TextField(blank=True)  # long text, always hidden unless requested

    response_policy = models.ForeignKey('ResponsePolicy', on_delete=models.CASCADE)
    suggested_responses = models.ManyToManyField('SuggestedResponse', blank=True)

    # Also available:
    #
    # self.condition_set.all()
    # self.suggestedresponse_set.all()
    # self.collectedinput_set.all()

    class Meta:
        ordering = ('order', 'pk')

    def __str__(self):
        return self.text

    def test_conditions(self, **context):
        """ Checks data all Conditions gating this instrument. """
        for condition in self.conditions.all():
            if not condition.test(**context):
                return False  # No fancy AND/OR/NONE logic, if one fails, the whole test fails
        return True


class ResponsePolicy(DatesModel, models.Model):
    """
    Flags that define an archetypical way to respond to a category of CollectionInstruments.
    CollectionInstruments may point to a common ResponsePolicy, or define separate instances for
    finer control over a specific CollectionInstrument's policy flags.
    """
    # Internal references
    nickname = models.CharField(max_length=100, null=True)
    is_singleton = models.BooleanField(default=False)

    # Flags for related CollectionInstrument(s)
    # NOTE: 'multiple' should be treated like a hint suggesting that a CollectedInput for an
    # instrument will be serialized to fit into the ``input.data`` field, and that it must be
    # deserialized later.
    restrict = models.BooleanField()  # must supply answer matching a SuggestedResponse
    multiple = models.BooleanField()  # allows multiple selections
    required = models.BooleanField()  # validation hint

    # TODO: Consider extra flags for response count limits here, allowing overrides to the
    # CollectionRequest limits.

    # Also available:
    #
    # self.collectioninstrument_set.all()

    class Meta:
        verbose_name_plural = 'Response policies'

    def __str__(self):
        return self.nickname or ':'.join(sorted(self.get_flags().items(), key=operator.itemgetter(0)))

    def get_flags(self):
        return {
            'restrict': self.restrict,
            'multiple': self.multiple,
            'required': self.required,
        }


class SuggestedResponse(DatesModel, models.Model):
    """
    A pre-identified valid response for a CollectionInstrument.
    """
    data = models.CharField(max_length=512)

    # Also available:
    #
    # self.collectioninstrument_set.all()

    def __str__(self):
        return str(self.data)


class AbstractCollectedInput(DatesModel, models.Model):
    """
    Abstract definition of a single point of data collected for a given Measure, related to the
    CollectionInstrument used to gather it. Many CollectedInputs are gathered in a
    CollectionRequest.

    A ``data`` field must be supplied by a concrete sublcass.
    """

    objects = managers.CollectedInputQuerySet.as_manager()

    # Note that these fk references MUST include this app's label, since otherwise, anyone
    # inheriting from this abstract base will end up with ForeignKey references that appear local.
    collection_request = models.ForeignKey('django_input_collection.CollectionRequest',
                                           related_name='collectedinput_set',
                                           on_delete=models.CASCADE)
    instrument = models.ForeignKey('django_input_collection.CollectionInstrument',
                                   related_name='collectedinput_set',
                                   on_delete=models.CASCADE)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)

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

    def serialize_data(self, data):
        """ Enforce strings for CharField compatibility. """
        return str(data)

    def deserialize_data(self, data):
        """ Pass data straight out as a string. """
        return data
