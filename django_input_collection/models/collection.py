# -*- coding: utf-8 -*-
import logging
from django.db import models
from django.db.models import Q
from django.conf import settings

import swapper

from . import managers
from .base import DatesModel
from ..apps import app

log = logging.getLogger(__name__)

_should_log, log_method = app.get_verbose_logging

__all__ = [
    "Measure",
    "CollectionRequest",
    "CollectionGroup",
    "CollectionInstrumentType",
    "CollectionInstrument",
    "ResponsePolicy",
    "AbstractBoundSuggestedResponse",
    "BoundSuggestedResponse",
    "SuggestedResponse",
    "AbstractCollectedInput",
    "CollectedInput",
]


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

    # Also available:
    #
    # self.segment_instruments.all()
    # self.group_instruments.all()

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
            "max_instrument_inputs_per_user": self.max_instrument_inputs_per_user,
            "max_instrument_inputs": self.max_instrument_inputs,
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

    objects = managers.CollectionInstrumentQuerySet.as_manager()

    collection_request = models.ForeignKey("CollectionRequest", on_delete=models.CASCADE)
    measure = models.ForeignKey("Measure", on_delete=models.CASCADE)
    segment = models.ForeignKey(
        "CollectionGroup",
        blank=True,
        null=True,
        related_name="segment_instruments",
        on_delete=models.SET_NULL,
    )
    group = models.ForeignKey(
        "CollectionGroup",
        blank=True,
        null=True,
        related_name="group_instruments",
        on_delete=models.SET_NULL,
    )
    type = models.ForeignKey(
        "CollectionInstrumentType", blank=True, null=True, on_delete=models.SET_NULL
    )

    order = models.IntegerField(default=0)

    text = models.TextField()
    description = models.TextField(blank=True)  # short text, always displayed
    help = models.TextField(blank=True)  # long text, always hidden unless requested

    response_policy = models.ForeignKey("ResponsePolicy", on_delete=models.CASCADE)
    suggested_responses = models.ManyToManyField(
        "SuggestedResponse", through=settings.INPUT_BOUNDSUGGESTEDRESPONSE_MODEL, blank=True
    )

    # Also available:
    #
    # self.conditions.all()  # Conditions toward enabling this instrument
    # self.bound_suggested_responses.all()
    # self.collectedinput_set.all()

    class Meta:
        ordering = ("segment_id", "order", "pk")

    def __str__(self):
        return self.text or "(No text)"

    def test_conditions(self, **kwargs):
        """Checks data all Conditions gating this instrument."""
        idx = 0
        for idx, condition in enumerate(self.conditions.all(), start=1):
            if not condition.test(**kwargs):
                if idx > 1 and _should_log:
                    log_method(f"Condition {idx}/{self.conditions.count()} FAILED")
                return False  # No fancy AND/OR/NONE logic, if one fails, the whole test fails
        if idx > 1 and _should_log:
            log_method(f"Conditions {idx}/{self.conditions.count()} PASSED")
        return True

    def get_parent_instruments(self):
        """
        Returns a list of instruments that enable this one via a Condition.
        """
        instruments = self.collection_request.collectioninstrument_set.all()
        parents = instruments.filter(conditions__instrument=self)
        parent_ids = []
        parent_measures = []
        parent_getters = list(parents.values_list("conditions__data_getter", flat=True))
        for spec in parent_getters:
            resolver, reference = spec.split(":", 1)
            if resolver == "instrument":
                # Parse the reference to find the parent
                try:
                    parent_ids.append(int(reference))
                except:
                    parent_measures.append(reference)
        return instruments.filter(
            Q(id__in=parent_ids) | Q(measure_id__in=parent_measures)
        ).distinct()

    def get_child_instruments(self):
        """Returns a list of instrument that this one enables via a Condition."""
        # TODO: Add Resolver syntax that yields this list, given an instrument
        data_getters = [
            "instrument:%d" % (self.pk,),
            "instrument:%s" % (self.measure_id,),
        ]
        instruments = self.collection_request.collectioninstrument_set.all()
        return instruments.filter(conditions__data_getter__in=data_getters)

    def get_child_conditions(self):
        from .conditions import Condition

        return Condition.objects.filter(data_getter="instrument:%d" % (self.pk,))

    def get_choices(self):
        """Returns a list of SuggestedResponse ``data`` values."""
        return list(self.suggested_responses.values_list("data", flat=True))


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
        verbose_name_plural = "Response policies"

    def __str__(self):
        return self.nickname or ":".join([f"{k}={v}" for k, v in self.get_flags().items()])

    def get_flags(self):
        return {
            "restrict": self.restrict,
            "multiple": self.multiple,
            "required": self.required,
        }


class AbstractBoundSuggestedResponse(DatesModel, models.Model):
    # NOTE: These fk references MUST include this app's label, since otherwise, anyone inheriting
    # from this abstract base will end up with ForeignKey references that appear local.
    collection_instrument = models.ForeignKey(
        "django_input_collection.CollectionInstrument",
        on_delete=models.CASCADE,
        related_name="bound_suggested_responses",
    )
    suggested_response = models.ForeignKey(
        "django_input_collection.SuggestedResponse", on_delete=models.CASCADE
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.suggested_response.data

    def clean(self, data):
        """Cleaning hook for primitive input generated by this SuggestedResponse."""
        return data


class BoundSuggestedResponse(AbstractBoundSuggestedResponse):
    """The m2m membership model for CollectionInstrument.suggested_responses."""

    class Meta:
        # swappable = 'INPUT_BOUNDSUGGESTEDRESPONSE_MODEL'
        swappable = swapper.swappable_setting("input", "BoundSuggestedResponse")


class SuggestedResponse(DatesModel, models.Model):
    """A pre-identified valid response for a CollectionInstrument."""

    data = models.CharField(max_length=512)

    # Also available:
    #
    # self.collectioninstrument_set.all()

    def __str__(self):
        if isinstance(self.data, bytes):
            return self.data.encode("utf-8")
        return self.data


class AbstractCollectedInput(DatesModel, models.Model):
    """
    Abstract definition of a single point of data collected for a given Measure, related to the
    CollectionInstrument used to gather it. Many CollectedInputs are gathered in a
    CollectionRequest.

    A ``data`` field must be supplied by a concrete sublcass.
    """

    objects = managers.CollectedInputQuerySet.as_manager()

    # NOTE: These fk references MUST include this app's label, since otherwise, anyone inheriting
    # from this abstract base will end up with ForeignKey references that appear local.
    collection_request = models.ForeignKey(
        "django_input_collection.CollectionRequest",
        related_name="collectedinput_set",
        on_delete=models.CASCADE,
    )
    instrument = models.ForeignKey(
        "django_input_collection.CollectionInstrument",
        related_name="collectedinput_set",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL
    )

    # Recordkeeping details
    version = models.CharField(max_length=128)
    collector_class = models.CharField(max_length=256)
    collector_id = models.CharField(max_length=64)
    collector_version = models.CharField(max_length=128)
    collector_comment = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.data)

    def get_context(self, fields=None):
        """
        Returns the context dict of this input's model field values.  If ``fields`` is given, it
        should be a whitelist list of fields that should appear in the returned dict.
        """

        if fields is None:
            fields = ["user"]

        return {field: getattr(self, field) for field in fields if self._meta.get_field(field)}

    def get_data_display(self, collector=None, method=None):
        """
        If ``method`` is given, then that method instance will render the input object.  If a
        ``collector`` is given instead, it will be used to look up a method for the input's
        instrument.  If no arguments are provided, the default method will coerce the object to
        unicode, as is the behavior of the default InputMethod class.
        """
        from ..collection import Collector

        if not collector and not method:
            context = self.get_context()
            collector = Collector(self.collection_request, **context)

        if collector and not method:
            method = collector.get_method(self.instrument)

        return method.get_data_display(self.data["input"])


class CollectedInput(AbstractCollectedInput):
    """
    A single point of data collected for a given Measure, related to the CollectionInstrument used
    to gather it.  Many CollectedInputs are gathered in a CollectionRequest.
    """

    data = models.CharField(max_length=512)

    class Meta:
        # swappable = 'INPUT_COLLECTEDINPUT_MODEL'
        swappable = swapper.swappable_setting("input", "CollectedInput")
