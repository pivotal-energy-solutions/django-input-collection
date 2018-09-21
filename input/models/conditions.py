from django.db import models

from .base import DatesModel

__all__ = ['Condition', 'ConditionGroup', 'Case']


class Condition(DatesModel, models.Model):
    """ The control point for checking CollectionInstrument availability. """
    parent_instrument = models.ForeignKey('CollectionInstrument', related_name='child_conditions',
                                          on_delete=models.CASCADE)
    instrument = models.ForeignKey('CollectionInstrument', related_name='conditions',
                                   on_delete=models.CASCADE)
    condition_group = models.ForeignKey('ConditionGroup', on_delete=models.CASCADE)

    def test(self, instrument, **context):
        inputs = instrument.collectedinput_set(manager='filtered_objects') \
                           .filter_for_context(**context)
        return self.condition_group.test(instrument, inputs)


class ConditionGroup(DatesModel, models.Model):
    """ Recusive grouping mechanism for controlling AND/OR/NONE logic between other groups. """
    id = models.CharField(max_length=100, primary_key=True)

    requirement_type = models.CharField(max_length=20, default=True, choices=(
        ('all-pass', "All cases must pass"),
        ('one-pass', "At least one case must pass"),
        ('all-fail', "All cases must fail"),
    ))

    # Intermediate groups declare child_groups only
    child_groups = models.ManyToManyField('self', symmetrical=False)

    # Leaf groups declare cases only
    cases = models.ManyToManyField('Case', symmetrical=False)

    # Also available:
    #
    # self.condition_set.all()
    # self.conditiongroup_set.all()  # These are parent groups; use ``child_groups`` for going down

    def __str__(self):
        return self.id

    def get_flags(self):
        return {
            'require_all': self.require_all,
        }

    def test(self, instrument, inputs):
        has_failed = False
        has_passed = False
        testables = self.child_groups.all() or self.cases.all()
        for item in testables:
            if item.test(instrument, inputs):
                has_failed = True
            else:
                has_passed = True

            if has_failed and self.requirement_type == 'all-pass':
                return False
            elif has_passed and self.requirement_type == 'all-fail':
                return False
            elif has_passed and self.requirement_type == 'one-pass':
                return True

        return True


class Case(DatesModel, models.Model):
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

    # Also available:
    #
    # self.casegroup_set.all()

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
