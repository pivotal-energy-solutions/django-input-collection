from __future__ import unicode_literals

import logging

from django.contrib import admin
from django.contrib.admin.templatetags.admin_list import _boolean_icon
from django.forms import fields_for_model, Textarea
from django.utils.safestring import mark_safe
from django.utils.html import format_html, format_html_join

from . import models


log = logging.getLogger(__name__)


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
    list_display = ['id', '_instrument', '_data_getter', '_test', 'condition_group']
    list_display_links = ['id', '_instrument']
    list_filter = ['date_created', 'date_modified']
    search_fields = ['instrument__text', 'data_getter', 'condition_group__nickname', 'condition_group__cases__nickname']
    date_hierarchy = 'date_created'

    readonly_fields = ['_resolver_info', '_test']
    fields = list(fields_for_model(models.Condition).keys()) + ['_resolver_info', '_test']

    def get_queryset(self, request):
        queryset = super(ConditionAdmin, self).get_queryset(request)
        self.request = request
        return queryset

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'data_getter':
            kwargs['widget'] = Textarea
        return super(ConditionAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    def _instrument(self, instance):
        return format_html('<div style="width: 200px;">{}</div>', instance.instrument)
    _instrument.short_description = """Instrument"""

    def _data_getter(self, instance):
        data_getter = mark_safe('<div>{}</div>'.format(instance.data_getter))
        return data_getter + self._resolver_info(instance)
    _data_getter.short_description = """Data Getter"""

    def _resolver_info(self, instance):
        if instance.pk is None:
            return '(Unsaved)'

        resolver, data, error = instance.resolve(raise_exception=False)
        if resolver:
            return format_html('<dt>{}</dt><dd>{}{}</dd>',
                '.'.join((resolver.__module__, resolver.__class__.__name__)),
                format_html('<code>{}</code>', repr(data)) if not error else '',
                format_html('<code style="color: orange;">Lookup failed!  (Will use collector class default.)<br>{}</code>', error) if error else '',
            )
        return format_html('<div style="color: red;">{}</div>',
            'NO MATCHING RESOLVER',
        )
    _resolver_info.short_description = """Resolver"""

    def _test(self, instance):
        try:
            from .collection.collectors import registry

            if instance.pk is None:
                return _boolean_icon(None)

            collection_request = instance.instrument.collection_request

            statuses = []
            context = {
                'user': self.request.user,
            }

            for collector_class in sorted(registry.values(), key=lambda c: (c.__module__, c.__name__)):
                status = '-'
                try:
                    collector = collector_class(collection_request=collection_request, context=context)
                    status = _boolean_icon(collector.is_condition_successful(instance, raise_exception=False))
                except Exception as e:
                    log.exception(e)
                    status = format_html('<code style="color: red;">{}</code>', e)
                statuses.append([
                    '.'.join((collector_class.__module__, collector_class.__name__)),
                    status,
                ])
            return mark_safe('<dl>%s</dl>' % (format_html_join('', '<dt>{}</dt><dd>{}</dd>', statuses),))
        except Exception as e:
            log.exception(e)
            return format_html('<code style="color: red;">{}</code>', e)
    _test.short_description = """Test"""


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
