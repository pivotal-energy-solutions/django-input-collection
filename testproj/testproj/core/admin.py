from django.contrib import admin

from input.models import (Measure, CollectionGroup, CollectionRequest, CollectionInstrument,
                          AbstractCollectedInput, get_input_model)

from .models import Survey, PoliticalRally, RallyPoll



@admin.register(Measure)
class MeasureAdmin(admin.ModelAdmin):
    pass


@admin.register(CollectionGroup)
class CollectionGroupAdmin(admin.ModelAdmin):
    pass


@admin.register(CollectionRequest)
class CollectionRequestAdmin(admin.ModelAdmin):
    pass


@admin.register(CollectionInstrument)
class CollectionInstrumentAdmin(admin.ModelAdmin):
    list_display = ('text', 'group', 'measure', 'collection_request')
    list_filter = ('group', 'measure')


@admin.register(get_input_model())
class CollectedInputAdmin(admin.ModelAdmin):
    pass


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    pass


@admin.register(PoliticalRally)
class PoliticalRallyAdmin(admin.ModelAdmin):
    pass


@admin.register(RallyPoll)
class RallyPollAdmin(admin.ModelAdmin):
    pass
