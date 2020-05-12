# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
import re
import operator
import six
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


log = logging.getLogger(__name__)


def set_substitutions(d):
    def decorator(f):
        f.__dict__.update(substitutions=d)
        return f
    return decorator


def substitute(s, substitutions):
    for pattern, rep in substitutions.items():
        s = re.sub(pattern, rep, s)
    return s



@six.python_2_unicode_compatible
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
        return '[%(instrument)r depends on resolver=%(resolver)r via %(condition_group)r]' % {
            'instrument': self.instrument,
            'resolver': self.data_getter.split(':')[0],
            'condition_group': self.condition_group,
        }

    def resolve(self, **kwargs):
        """
        Finds a resolver class for ``self.data_getter`` and returns a 3-tuple of the resolver,
        the data yielded by the it, and any error raised during attribute traversal.
        """
        kwargs.update(kwargs.pop('context', None) or {})
        resolver, data_info, error = resolvers.resolve(self.instrument, self.data_getter, **kwargs)

        if resolver and (not isinstance(data_info, dict) or 'data' not in data_info):
            raise ValueError("Resolver '%s' did not return a dict with a 'data' key: %r" % (
                resolver.__class__.__name__, data_info
            ))
        return resolver, data_info, error

    def test(self, **kwargs):
        """
        Resolves and runs the ``data_getter`` value and sends it to the related ``condition_group``.
        ``kwargs`` are forwarded through condtion group hierarchies and sent to
        ``collection.matchers.test_condition_case()``.
        """
        resolver_kwargs = {}
        if 'raise_exception' in kwargs:
            resolver_kwargs['raise_exception'] = kwargs.pop('raise_exception')
        if 'context' in kwargs:
            resolver_kwargs['context'] = kwargs.pop('context')
        if 'resolver_fallback_data' in kwargs:
            resolver_kwargs['fallback'] = kwargs.pop('resolver_fallback_data')
        resolver, data_info, error = self.resolve(**resolver_kwargs)

        kwargs.update(data_info)

        # We will allow the condition test to run even if there is an error, since a 'fallback'
        # value might ensure that resolution-related errors are kept quiet.  It will be up to the
        # resolver to raise errors that prevent the test from even happening.
        value = self.condition_group.test(**kwargs)
        log.info("Instrument Condition Group - %s (%s) Test Result: %s",
                 self.condition_group, self.condition_group.pk, value)
        return value


@six.python_2_unicode_compatible
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

        _should_log = False
        # if isinstance(data, list) and len(data):
        #     _should_log = True
        # elif isinstance(data, dict) and data.get('input'):
        #     _should_log = True

        if testables and _should_log:
            log.debug("%d Tests will be conducted on ConditionGroup (%s) using %r",
                      len(testables), self.pk, data)
        for item in testables:
            if item.test(data, **kwargs):
                has_passed = True
            else:
                has_failed = True

            if has_failed and self.requirement_type == 'all-pass':
                if _should_log:
                    log.debug("{} ({}) {} Conditional all-pass Group: {} - FAIL".format(
                        self.nickname, self.pk, len(testables), item.describe()))
                return False
            elif has_passed and self.requirement_type == 'all-fail':
                if _should_log:
                    log.debug("{} ({}) {} Conditional all-fail Group: {} - FAIL".format(
                        self.nickname, self.pk, len(testables), item.describe()))
                return False
            elif has_passed and self.requirement_type == 'one-pass':
                if _should_log:
                    log.debug("{} ({}) {} Conditional one-pass Group: {} - TRUE".format(
                        self.nickname, self.pk, len(testables), item.describe()))
                return True

        if not has_passed and self.requirement_type == 'one-pass':
            if _should_log:
                log.debug("{} ({}) {} Conditional one-pass Group: ALL FAILED".format(
                          self.nickname, self.pk, len(testables)))
            return False

        if _should_log:
            log.debug("{} ({}) {} Conditional Group: ALL PASSED".format(
                      self.nickname, self.pk, len(testables)))
        return True


@six.python_2_unicode_compatible
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

        # Partial, relies on ``match_data`` field
        ('match', "Input matches this data"),
        ('mismatch', "Input doesn't match this data"),
        ('greater_than', "Input is greater than this data"),
        ('less_than', "Input is less than this data"),
        ('contains', "Input contains this data"),
        ('not-contains', "Input does not contain this data"),
        ('one', "Input is in these values"),
        ('zero', "Input is not in these values"),
    ))
    match_data = models.CharField(max_length=512, blank=True, null=True)

    # Also available:
    #
    # self.conditiongroup_set.all()

    def __str__(self):
        return self.nickname or self.describe().decode('utf-8')

    def get_flags(self):
        return {
            'match_type': self.match_type,
            'match_data': self.match_data,
        }

    @set_substitutions(OrderedDict((
        (r"^Input (.*)", r'\1'),
        (r"matches this data", '={data}'),
        (r"doesn't match this data", '≠{data}'),
        (r"is greater than this data", '>{data}'),
        (r"is less than this data", '<{data}'),
        (r"contains this data", '*{data}*'),
        (r"doesn't contain this data", '!*{data}*'),
        (r"is in these values", 'in {data}'),
        (r"doesn't contain this data", '!in {data}'),
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
