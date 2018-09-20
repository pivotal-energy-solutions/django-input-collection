from django.db import models

from .base import DatesModel

__all__ = ['Condition', 'ConditionGroup', 'ConditionCase']


class Condition(DatesModel, models.Model):
    """ The control point for offering a CollectionInstrument under the correct conditions. """
    instrument = models.ForeignKey('CollectionInstrument', on_delete=models.CASCADE)
    case_group = models.ForeignKey('ConditionGroup', on_delete=models.CASCADE)

    def test(self, instrument, **context):
        inputs = instrument.collectedinput_set(manager='filtered_objects') \
                           .filter_for_context(**context)
        return self.case_group.test(instrument, inputs)


class ConditionGroup(DatesModel, models.Model):
    id = models.CharField(max_length=100, primary_key=True)

    parent_group = models.ForeignKey('self', blank=True, null=True, on_delete=models.CASCADE)
    cases = models.ManyToManyField('ConditionCase')

    require_all = models.CharField(max_length=20, default=True, choices=(
        ('all-pass', "All cases must pass"),
        ('one-pass', "At least one case must pass"),
        ('all-fail', "All cases must fail"),
    ))

    def __str__(self):
        return self.id

    def get_flags(self):
        return {
            'require_all': self.require_all,
        }

    def test(self, instrument, inputs):
        for case in self.cases.all():
            if not case.test(instrument, inputs):
                if self.require_all:
                    return False
        return True


class ConditionCase(DatesModel, models.Model):
    id = models.CharField(max_length=100, primary_key=True)

    has_response = models.CharField(max_length=20, default='any', null=True, choices=(
        ('any', "Any input allowed"),
        ('none', "No input allowed"),
        (None, "(No requirement)"),
    ))
    has_response_type = models.CharField(max_length=20, default=None, null=True, choices=(
        ('all-suggested', "All suggested"),
        ('one-suggested', "At least one suggested"),
        ('all-custom', "All custom"),
        ('one-custom', "At least one custom"),
        (None, "(No requirement)"),
    ))
    has_matching_data = models.CharField(max_length=20, default=None, null=True, choices=(
        ('match', "Input matches this data"),
        ('contains', "Input contains this data"),
        ('not-contains', "Input does not contain this data"),
        ('mismatch', "Input doesn't match this data"),
        (None, "(No requirement)"),
    ))
    data = models.CharField(max_length=512)

    def __str__(self):
        return self.id

    def get_flags(self):
        return {
            'has_response': self.has_response,
            'has_response_type': self.has_response_type,
            'has_matching_data': self.has_matching_data,
            'data': self.data,
        }

    def test(self, instrument, inputs):
        return False  # TODO


