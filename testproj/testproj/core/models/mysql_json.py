from django.db import models

from django_mysql.models import JSONField, QuerySet as JsonAware_QuerySet
from input.models import AbstractCollectedInput

__all__ = ['CollectedInput_MySQL_JSON']


class CollectedInput_MySQL_JSON(AbstractCollectedInput):
    objects = JsonAware_QuerySet.as_manager()

    data = JSONField()
