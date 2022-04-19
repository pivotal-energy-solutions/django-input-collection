# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import Survey, PoliticalRally, RallyPoll


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    pass


@admin.register(PoliticalRally)
class PoliticalRallyAdmin(admin.ModelAdmin):
    pass


@admin.register(RallyPoll)
class RallyPollAdmin(admin.ModelAdmin):
    pass
