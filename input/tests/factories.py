# factoryboy

from django.conf import settings

import factory

class MeasureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'input.Measure'
        django_get_or_create = ('id',)

    id = factory.Sequence(lambda n: 'measure-%d' % n)


class CollectionGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'input.CollectionGroup'
        django_get_or_create = ('id',)

    id = 'default'


class CollectionRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'input.CollectionRequest'
        django_get_or_create = ('id',)

    id = factory.Sequence(lambda n: n + 1)
    max_instrument_inputs_per_user = 1
    max_instrument_inputs = None


class ResponsePolicyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'input.ResponsePolicy'
        django_get_or_create = ('nickname',)

    nickname = 'default'
    restrict = False
    multiple = False


class SuggestedResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'input.SuggestedResponse'
        django_get_or_create = ('id',)

    id = factory.Sequence(lambda n: n + 1)
    data = factory.Sequence(lambda n: 'response %d' % n)


class CollectionInstrumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'input.CollectionInstrument'
        django_get_or_create = ('id',)

    id = factory.Sequence(lambda n: n + 1)
    collection_request = factory.SubFactory(CollectionRequestFactory)
    measure = factory.SubFactory(MeasureFactory)
    group = factory.SubFactory(CollectionGroupFactory, id='default')
    response_policy = factory.SubFactory(ResponsePolicyFactory)

    order = factory.Sequence(lambda n: n)
    text = factory.Sequence(lambda n: 'text %d' % n)
    description = factory.Sequence(lambda n: 'description %d' % n)
    help = factory.Sequence(lambda n: 'help %d' % n)

    @factory.post_generation
    def suggested_responses(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.suggested_responses.add(*extracted)


class CollectedInputFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = settings.INPUT_COLLECTEDINPUT_MODEL
        django_get_or_create = ('id',)

    id = factory.Sequence(lambda n: n + 1)
    collection_request = factory.SubFactory(CollectionRequestFactory)
    instrument = factory.SubFactory(CollectionInstrumentFactory, **{
        'collection_request': factory.SelfAttribute('..collection_request'),
    })
    data = factory.Sequence(lambda n: {'answer': n})  # FIXME: Assumes json