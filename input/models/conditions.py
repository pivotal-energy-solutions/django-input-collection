from django.db import models

from .base import DatesModel

__all__ = ['Condition', 'ConditionGroup', 'Case']


class Condition(DatesModel, models.Model):
    """ The control point for checking CollectionInstrument availability. """
    instrument = models.ForeignKey('CollectionInstrument', related_name='conditions',
                                   on_delete=models.CASCADE)
    parent_instrument = models.ForeignKey('CollectionInstrument', related_name='child_conditions',
                                          on_delete=models.CASCADE)
    condition_group = models.ForeignKey('ConditionGroup', on_delete=models.CASCADE,
                                        limit_choices_to={'parent_groups': None})

    def __str__(self):
        return '[instrument=%r depends on instrument=%r via %r]' % (
            self.instrument_id,
            self.parent_instrument_id,
            self.condition_group_id,
        )

    def test(self, **context):
        # Testing the availability of ``instrument`` relies on ``parent_instrument`` conditions.
        test = self.condition_group.test(self.parent_instrument, **context)
        return test


class ConditionGroup(DatesModel, models.Model):
    """ Recusive grouping mechanism for controlling AND/OR/NONE logic between other groups. """

    nickname = models.CharField(max_length=100, unique=True, blank=True, null=True)
    requirement_type = models.CharField(max_length=20, default=True, choices=(
        ('all-pass', "All cases must pass"),
        ('one-pass', "At least one case must pass"),
        ('all-fail', "All cases must fail"),
    ))

    # Intermediate groups declare child_groups only
    child_groups = models.ManyToManyField('self', related_name='parent_groups', blank=True,
                                          symmetrical=False)

    # Leaf groups declare cases only
    cases = models.ManyToManyField('Case', symmetrical=False)

    # Also available:
    #
    # self.condition_set.all()
    # self.parent_groups.all()
    # self.cases.all()

    def __str__(self):
        return self.nickname or self.id

    def get_flags(self):
        return {
            'requirement_type': self.requirement_type,
        }

    def test(self, instrument_or_raw_values, **kwargs):
        has_failed = False
        has_passed = False
        testables = self.child_groups.all() or self.cases.all()
        for item in testables:
            if item.test(instrument_or_raw_values, **kwargs):
                has_passed = True
            else:
                has_failed = True

            if has_failed and self.requirement_type == 'all-pass':
                return False
            elif has_passed and self.requirement_type == 'all-fail':
                return False
            elif has_passed and self.requirement_type == 'one-pass':
                return True

        if not has_passed and self.requirement_type == 'one-pass':
            return False

        return True


class Case(DatesModel, models.Model):
    nickname = models.CharField(max_length=100, unique=True, blank=True, null=True)

    match_type = models.CharField(max_length=20, default=None, null=True, choices=(
        # Generic
        ('any', "Any input allowed"),
        ('none', "No input allowed"),

        # Suggested vs custom
        ('all-suggested', "All suggested"),
        ('one-suggested', "At least one suggested"),
        ('all-custom', "All custom"),
        ('one-custom', "At least one custom"),

        # Partial, relies on ``data`` field
        ('match', "Input matches this data"),
        ('mismatch', "Input doesn't match this data"),
        ('contains', "Input contains this data"),
        ('not-contains', "Input does not contain this data"),
    ))
    match_data = models.CharField(max_length=512)

    # Also available:
    #
    # self.conditiongroup_set.all()

    def __str__(self):
        return self.nickname or self.id

    def get_flags(self):
        return {
            'match_type': self.match_type,
            'match_data': self.match_data,
        }

    def test(self, instrument_or_raw_values, **kwargs):
        from ..collection.utils import test_condition_case

        flags = self.get_flags()
        return test_condition_case(instrument_or_raw_values, **flags, **kwargs)
