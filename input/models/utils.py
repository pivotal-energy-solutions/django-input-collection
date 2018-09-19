from django.db import models

import swapper


def get_input_model():
    return swapper.load_model('input', 'CollectedInput')


def isolate_response_policy(instrument):
    """
    Ensures the response_policy instance is unique to this CollectionInstrument and marked for
    disallowing future reuse.  If ``instrument`` is the only instance related to its
    ResponsePolicy (i.e., the policy is already isolated), then no work is performed.
    """
    policy = instrument.response_policy
    has_other_uses = policy.collectioninstrument_set.exclude(pk=instrument.pk).exists()
    if has_other_uses:
        instrument.response_policy = clone_response_policy(policy)
        instrument.save()


def clone_response_policy(response_policy, **kwargs):
    """
    Creates a new ResponsePolicy with identical flags.  All kwargs are forwarded to the manager's
    create() method to allow for easy overrides.
    """

    from .models import ResponsePolicy

    if 'nickname' not in kwargs:
        nickname = 'Cloned pk={pk}, {kwargs!r}'.format(**{
            'pk': response_policy.pk,
            'kwargs': kwargs,  # includes processed 'is_singletone' value
        })

        # Trim to max length
        max_length = response_policy._meta.get_field('nickname').max_length
        overflow_count = len(nickname[max_length:])
        if overflow_count:
            nickname = nickname[:-(3 + overflow_count)] + '...'

    # Get a clean set of kwargs where the called ``**kwargs`` override the defaults.
    create_kwargs = response_policy.get_flags()
    create_kwargs.update(kwargs)

    policy = ResponsePolicy.objects.create(**create_kwargs)
    return policy

