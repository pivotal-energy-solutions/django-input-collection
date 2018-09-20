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

instrument_kwargs = {
    'collection_request__id': 1,
    'response_policy__nickname': 'default',
}

# Default, no suggestions
factories.CollectionInstrumentFactory.create(**instrument_kwargs)

# Open response with suggestions
factories.CollectionInstrumentFactory.create(**dict(instrument_kwargs, **{
    'suggested_responses': suggested_responses,
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
