from django.db import models
from django.contrib.auth.models import AnonymousUser
from django.conf import settings

import swapper

from .. import collection
from . import managers

__all__ = ['Measure', 'CollectionRequest', 'CollectionGroup', 'CollectionInstrument',
           'ResponsePolicy', 'SuggestedResponse', 'AbstractCollectedInput', 'CollectedInput']


class DatesModel(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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

    # NOTE: An Instrument that allows select-multiple answers that should counted as only a single
    # submission must serialize that plural data for strorage on a single CollectedInput, to be
    # unserialized later.
    max_instrument_inputs_per_user = models.PositiveIntegerField(blank=True, null=True)

    # Maximum inputs across all users for any single Instrument.
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
    suggested_responses = models.ManyToManyField('SuggestedResponse')  # FIXME: ordering?

    # TODO: Consider response count limits here, allowing per-instrument overrides to the
    # CollectionRequest limits.

    # Also available:
    #
    # self.suggestedresponse_set.all()
    # self.collectedinput_set.all()

    class Meta:
        ordering = ('order', 'pk')

    def __str__(self):
        return self.text

    def receive(self, data):
        return collection.store(self, data)


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

    # Also available:
    #
    # self.collectioninstrument_set.all()

    def get_flags(self):
        return {
            'restrict': self.restrict,
            'multiple': self.multiple,
        }


class SuggestedResponse(DatesModel, models.Model):  # FIXME: swappable core for 'data'
    """
    A pre-identified valid response for a CollectionInstrument.
    """
    data = models.CharField(max_length=512)

    # Also available:
    #
    # self.collectioninstrument_set.all()


class AbstractCollectedInput(DatesModel, models.Model):
    """
    Abstract definition of a single point of data collected for a given Measure, related to the
    CollectionInstrument used to gather it. Many CollectedInputs are gathered in a
    CollectionRequest.

    A ``data`` field must be supplied by a concrete sublcass.
    """

    objects = models.Manager()

    # This custom manager is where restricted queryset behavior is allowed in swapped models.  It
    # is reasonable to subclass the provided custom QuerySet to indicate special filtering is meant
    # for this custom manager attribute.
    filtered_objects = managers.ContextualCollectedInputQuerySet.as_manager()

    # Note that these fk references MUST include this app's label, since otherwise, anyone
    # inheriting from this abstract base will end up with ForeignKey references that appear local.
    collection_request = models.ForeignKey('input.CollectionRequest',
                                           related_name='collectedinput_set',
                                           on_delete=models.CASCADE)
    instrument = models.ForeignKey('input.CollectionInstrument', related_name='collectedinput_set',
                                   on_delete=models.CASCADE)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.data)

    @classmethod
    def allowed_for_instrument(cls, instrument, **context):
        """
        Returns True when the given instrument passes checks against flags on its CollectionRequest.
        Note that if the CollectedInput model has been swapped and a ``user`` ForeignKey is NOT
        available, CollectionRequest.max_instrument_inputs_per_user CANNOT be respected.
        """

        user = context.get('user')
        if user and not isinstance(user, AnonymousUser):
            user_max = instrument.collection_request.max_instrument_inputs_per_user
            user_count = instrument.collectedinput_set.filter_for_user(user).count()
            if user_count >= user_count:
                return False

        instrument.collectedinput_set.all().count()
        instrument.collection_request.max_instrument_inputs

    @classmethod
    def clean_data_for_instrument(cls, instrument, data, **context):
        # Clean coded ids
        has_suggested_responses = instrument.suggested_responses.exists()
        if has_suggested_responses:
            is_single = (not instrument.response_policy.multiple)

            if is_single:
                data = [data]

            data = collection.get_data_for_suggested_responses(instrument, *data)

            if is_single:
                data = data[0]

        return data

    # These default implementations trust the type to match whatever modelfield is in use for the
    # ``data`` field on the concrete model.
    def serialize_data(self, data):
        """ Coerces ``data`` for storage on the active input model (CollectedInput or swapped). """
        return data

    def deserialize_data(self, data):
        """
        Coerces retrieved ``data`` from the active input model (CollectedInput or swapped) to an
        appropriate object for its type.
        """
        return data


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
