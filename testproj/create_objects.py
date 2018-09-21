import django; django.setup()
from django.contrib.auth import get_user_model; User = get_user_model()

from input.tests import factories


user, _ = User.objects.get_or_create(username='admin', defaults={
    'is_staff': True,
    'is_superuser': True,
})
user.set_password('admin')
user.save()


suggested_responses = [
    factories.SuggestedResponseFactory.create(data='Yes'),
    factories.SuggestedResponseFactory.create(data='No'),
    factories.SuggestedResponseFactory.create(data='Maybe'),
]


# Triggers when suggested responses only
casegroup_only_suggested = factories.ConditionGroupFactory.create(**{
    'id': 'gimme-only-suggested',
    'requirement_type': 'all-pass',
    'cases': [factories.CaseFactory.create(has_response_type='all-suggested')],
})
# Triggers when at least one suggested response
casegroup_any_suggested = factories.ConditionGroupFactory.create(**{
    'id': 'gimme-one-suggested',
    'requirement_type': 'all-pass',
    'cases': [factories.CaseFactory.create(has_response_type='one-suggested')],
})
# Triggers when custom responses only
casegroup_only_custom = factories.ConditionGroupFactory.create(**{
    'id': 'gimme-only-custom',
    'requirement_type': 'all-pass',
    'cases': [factories.CaseFactory.create(has_response_type='all-custom')],
})
# Triggers when at least one custom response
casegroup_any_custom = factories.ConditionGroupFactory.create(**{
    'id': 'gimme-one-custom',
    'requirement_type': 'all-pass',
    'cases': [factories.CaseFactory.create(has_response_type='one-custom')],
})




instrument_kwargs = {
    'collection_request__id': 1,
    'response_policy__nickname': 'default',
}

# Default, no suggestions
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'text': "Free response",
}))

# Open response with suggestions
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'text': "Free response (with suggestions)",
    'suggested_responses': suggested_responses,
}))

# Dependents (must be defined in reverse--inner 'instrument' reference is the parent)
factories.ConditionFactory.create(**{
    'parent_instrument': factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
        'text': "Free response (with suggestions) (suggestions trigger more)",
        'suggested_responses': suggested_responses,
    })),
    'condition_group__id': 'gimme-only-suggested',
    'instrument': factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
        'text': "Free response A (depends on above)",
    })),
})
factories.ConditionFactory.create(**{
    'parent_instrument': factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
        'text': "Free response (with suggestions) (custom triggers more)",
        'suggested_responses': suggested_responses,
    })),
    'condition_group__id': 'gimme-only-custom',
    'instrument': factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
        'text': "Free response B (depends on above)",
    })),
})

# Multiple choice, no "Other" answer
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'text': "Multiple choice",
    'response_policy__nickname': 'restrict',
    'response_policy__restrict': True,
    'suggested_responses': suggested_responses,
}))

# Multiple choice, select-multiple
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'text': "Multiple choice (pick all that apply)",
    'response_policy__nickname': 'multiple-restrict',
    'response_policy__multiple': True,
    'response_policy__restrict': True,
    'suggested_responses': suggested_responses,
}))

# Multiple choice, select-multiple, "Other" allowed
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'text': "Multiple choice (pick all that apply or enter custom)",
    'response_policy__nickname': 'multiple',
    'response_policy__multiple': True,
    'suggested_responses': suggested_responses,
}))
