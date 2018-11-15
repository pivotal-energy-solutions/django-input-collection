# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import re
import operator
from collections import OrderedDict
try:
    from functools import reduce
except:
    pass

from django.db import models

from ..collection import matchers
from ..collection import resolvers
from .base import DatesModel
from .utils import ConditionNode

__all__ = ['Condition', 'ConditionGroup', 'Case']


def set_substitutions(d):
    def decorator(f):
        f.__dict__.update(substitutions=d)
        return f
    return decorator


def substitute(s, substitutions):
    for pattern, rep in substitutions.items():
        s = re.sub(pattern, rep, s)
    return s


class Condition(DatesModel, models.Model):
    """
    Condition that relates a conditional CollectionInstrument to a ConditionGroup.  The
    ``data_getter`` field must point to source data that will be tested in the related
    ``condition_group``.
    """
    # NOTE: The decision to have the ``instrument`` fk here and a reverse relation 'conditions' on
    # that instrument is in service of allowing disparate getter references to be met before the
    # dependent instrument is unlocked.

    instrument = models.ForeignKey('CollectionInstrument', related_name='conditions',
                                   on_delete=models.CASCADE)
    condition_group = models.ForeignKey('ConditionGroup', on_delete=models.CASCADE,
                                        limit_choices_to={'parent_groups': None})
    data_getter = models.CharField(max_length=512)

    def __str__(self):
        return '[%(instrument)r depends on source=%(source)r via %(condition_group)r]' % {
            'instrument': self.instrument,
            'source': self.data_getter,
            'condition_group': self.condition_group,
        }

    def test(self, context=None, resolver_default=None, **kwargs):
        """
        Resolves and runs the ``data_getter`` value and sends it to the related ``condition_group``.
        ``kwargs`` are forwarded to ``collection.matchers.test_condition_case()``.  If the resolver
        encounters an error while evaluating the ``data_getter`` spec, the ``resolver_default`` dict
        will be used for kwargs in place of the anticipated resolver dict result.

        If CollectedInput is swapped and uses a complex ``data`` field type, you should use the
        ``resolver_default`` kwarg to ensure this method falls back to a compatible data format.
        """
        if context is None:
            context = {}
        if resolver_default is None:
            resolver_default = {'data': None}
        data_kwargs = resolvers.resolve(self.instrument, self.data_getter, default=resolver_default,
                                        **context)
        kwargs.update(data_kwargs)
        return self.condition_group.test(**kwargs)


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
    cases = models.ManyToManyField('Case', blank=True, symmetrical=False)

    # Also available:
    #
    # self.condition_set.all()
    # self.parent_groups.all()
    # self.cases.all()

    def __str__(self):
        return self.nickname or self.describe()

    def get_flags(self):
        return {
            'requirement_type': self.requirement_type,
        }

    @set_substitutions({
        'all-pass': operator.and_,
        'one-pass': operator.or_,
        'all-fail': lambda x,y: operator.and_(x, ~y),
    })
    def describe(self):
        if not self.pk:
            return '(Unsaved)'

        testables = list(self.child_groups.all()) + list(self.cases.all())
        if len(testables) == 0:
            return '(Empty)'

        substitution = self.describe.substitutions[self.requirement_type]
        tree = reduce(lambda a, b: substitution(a, ConditionNode(b)), testables, ConditionNode())
        return str(tree)

    def test(self, data, **kwargs):
        has_failed = False
        has_passed = False
        testables = list(self.child_groups.all()) + list(self.cases.all())
        for item in testables:
            if item.test(data, **kwargs):
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
    match_data = models.CharField(max_length=512, blank=True, null=True)

    # Also available:
    #
    # self.conditiongroup_set.all()

    def __str__(self):
        return self.nickname or self.describe()

    def get_flags(self):
        return {
            'match_type': self.match_type,
            'match_data': self.match_data,
        }

    @set_substitutions(OrderedDict((
        (r"^Input (.*)", r'\1'),
        (r"matches this data", '={data}'),
        (r"doesn't match this data", '≠{data}'),
        (r"contains this data", '*{data}*'),
        (r"doesn't contain this data", '!*{data}*'),
    )))
    def describe(self):
        if not self.pk:
            return '(Unsaved)'

        type_display = self.get_match_type_display()
        text = substitute(type_display, self.describe.substitutions)
        text = text.format(data=self.match_data)
        return text.encode('utf-8')

    def test(self, data, **kwargs):
        kwargs.update(self.get_flags())
        return matchers.test_condition_case(data, **kwargs)
