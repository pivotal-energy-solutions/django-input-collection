from django_mysql.models import JSONField, QuerySet as JsonAware_QuerySet
from input.models import AbstractCollectedInput
from input.models.managers import UserLatestCollectedInputQuerySet

__all__ = ['CollectedInput_MySQL_JSON']


class CollectedInput_MySQL_JSON(AbstractCollectedInput):
    objects = JsonAware_QuerySet.as_manager()
    filtered_objects = UserLatestCollectedInputQuerySet.as_manager()

    data = JSONField()
