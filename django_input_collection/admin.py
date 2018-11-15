from __future__ import unicode_literals

from django.contrib import admin
from django.forms import fields_for_model, Textarea
from django.utils.safestring import mark_safe
from django.utils.html import format_html_join

from . import models


@admin.register(models.Measure, models.CollectionGroup, models.CollectionInstrumentType)
class IdObjectAdmin(admin.ModelAdmin):
    list_display = ['id']
    list_filter = ['date_created', 'date_modified']
    date_hierarchy = 'date_created'


@admin.register(models.CollectionRequest)
class CollectionRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'max_instrument_inputs_per_user', 'max_instrument_inputs']
    list_filter = ['date_created', 'date_modified']
    date_hierarchy = 'date_created'


@admin.register(models.CollectionInstrument)
class CollectionInstrumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'collection_request', 'measure', 'group', 'type', '_text_preview',
                    '_has_description', '_has_help', 'response_policy', '_suggested_responses']
    list_filter = ['date_created', 'date_modified', 'group', 'type', 'response_policy']
    date_hierarchy = 'date_created'
    search_fields = ['measure_id', 'group_id', 'type_id', 'text', 'description', 'help']

    def _text_preview(self, instance):
        max_length = self._text_preview.max_length
        excess = len(instance.text[max_length:])
        ellipsis = '...' if excess else ''
        return instance.text[:max_length - len(ellipsis)] + ellipsis
    _text_preview.short_description = """Text"""
    _text_preview.max_length = 100

    def _has_description(self, instance):
        return bool(instance.description)
    _has_description.short_description = """Has description"""
    _has_description.boolean = True

    def _has_help(self, instance):
        return bool(instance.help)
    _has_help.short_description = """Has help"""
    _has_help.boolean = True

    def _suggested_responses(self, instance):
        queryset = instance.suggested_responses
        if queryset:
            return '; '.join(queryset.values_list('data', flat=True))
        return '(None)'
    _suggested_responses.short_description = """Suggested responses"""


@admin.register(models.ResponsePolicy)
class ResponsePolicyAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'restrict', 'multiple', 'required', 'is_singleton']
    list_filter = ['date_created', 'date_modified', 'restrict', 'multiple', 'required', 'is_singleton']
    date_hierarchy = 'date_created'
    ordering = ('nickname',)


@admin.register(models.SuggestedResponse)
class SuggestedResponseAdmin(admin.ModelAdmin):
    list_display = ['id', 'data']
    list_display_links = ['data']
    list_filter = ['date_created', 'date_modified']
    date_hierarchy = 'date_created'


@admin.register(models.get_input_model())
class CollectedInputAdmin(admin.ModelAdmin):
    list_display = ['id', 'data']
    list_filter = ['date_created', 'date_modified']
    search_fields = ['data']
    date_hierarchy = 'date_created'

    
@admin.register(models.Condition)
class ConditionAdmin(admin.ModelAdmin):
    list_display = ['id', 'data_getter', 'instrument', 'condition_group']
    list_filter = ['date_created', 'date_modified']
    search_fields = ['instrument__text', 'data_getter', 'condition_group__nickname', 'condition_group__cases__nickname']
    date_hierarchy = 'date_created'

    fields = ('data_getter', 'instrument', 'condition_group')
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'data_getter':
            kwargs['widget'] = Textarea
        return super(ConditionAdmin, self).formfield_for_dbfield(db_field, **kwargs)



@admin.register(models.ConditionGroup)
class ConditionGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'nickname', 'requirement_type', '_n_child_groups', '_n_cases']
    list_display_links = ['id', 'nickname']
    list_filter = ['date_created', 'date_modified']
    date_hierarchy = 'date_created'
    filter_horizontal = ['child_groups', 'cases']
    readonly_fields = ['describe']
    fields = ['describe'] + list(fields_for_model(models.ConditionGroup).keys())

    def _n_child_groups(self, instance):
        queryset = instance.child_groups.all()
        if queryset:
            return mark_safe('<ul>%s</ul>' % (
                format_html_join('\n', '<li>{}</li>', ([obj.describe()] for obj in queryset)),
            ))
        return '(None)'
    _n_child_groups.short_description = """Child groups"""

    def _n_cases(self, instance):
        queryset = instance.cases.all()
        if queryset:
            return mark_safe('<ul>%s</ul>' % (
                format_html_join('\n', '<li>{}</li>', ([obj.describe()] for obj in queryset)),
            ))
        return '(None)'
    _n_cases.short_description = """Cases"""


@admin.register(models.Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'nickname', 'match_type', 'match_data']
    list_display_links = ['id', 'nickname']
    list_filter = ['date_created', 'date_modified']
    date_hierarchy = 'date_created'
    filter_horizontal = ['conditiongroup']
    readonly_fields = ['describe']
