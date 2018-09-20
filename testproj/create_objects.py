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
casegroup_only_suggested = factories.CaseGroupFactory.create(**{
    'id': 'gimme-only-suggested',
    'require_all': True,
    'condition_group': factories.ConditionGroupFactory.create(**{
        'id': 'gimme-only-suggested',
        'require_all': True,
    }),
    'cases': [factories.CaseFactory.create(has_response_type='all-suggested')],
})
# Triggers when at least one suggested response
casegroup_any_suggested = factories.CaseGroupFactory.create(**{
    'id': 'gimme-one-suggested',
    'require_all': True,
    'condition_group': factories.ConditionGroupFactory.create(**{
        'id': 'gimme-one-suggested',
        'require_all': True,
    }),
    'cases': [factories.CaseFactory.create(has_response_type='one-suggested')],
})
# Triggers when custom responses only
casegroup_only_custom = factories.CaseGroupFactory.create(**{
    'id': 'gimme-only-custom',
    'require_all': True,
    'condition_group': factories.ConditionGroupFactory.create(**{
        'id': 'gimme-only-custom',
        'require_all': True,
    }),
    'cases': [factories.CaseFactory.create(has_response_type='all-custom')],
})
# Triggers when at least one custom response
casegroup_any_custom = factories.CaseGroupFactory.create(**{
    'id': 'gimme-one-custom',
    'require_all': True,
    'condition_group': factories.ConditionGroupFactory.create(**{
        'id': 'gimme-one-custom',
        'require_all': True,
    }),
    'cases': [factories.CaseFactory.create(has_response_type='one-custom')],
})




instrument_kwargs = {
    'collection_request__id': 1,
    'response_policy__nickname': 'default',
}

# Default, no suggestions
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
}))

# Open response with suggestions
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'suggested_responses': suggested_responses,
}))
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'suggested_responses': suggested_responses,
    'condition_set': [factories.ConditionFactory.create(**{
        'condition_group__id': 'gimme-only-suggested',
        'instrument': factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
        })),
    })],
}))
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'suggested_responses': suggested_responses,
    'condition_set': [factories.ConditionFactory.create(**{
        'condition_group__id': 'gimme-only-custom',
        'instrument': factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
        })),
    })],
}))

# Multiple choice, no "Other" answer
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'response_policy__nickname': 'restrict',
    'response_policy__restrict': True,
    'suggested_responses': suggested_responses,
}))

# Multiple choice, select-multiple
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'response_policy__nickname': 'multiple-restrict',
    'response_policy__multiple': True,
    'response_policy__restrict': True,
    'suggested_responses': suggested_responses,
}))

# Multiple choice, select-multiple, "Other" allowed
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'response_policy__nickname': 'multiple',
    'response_policy__multiple': True,
    'suggested_responses': suggested_responses,
}))
