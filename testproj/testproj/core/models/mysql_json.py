from django.db import models

from django_mysql.models import QuerySet as JsonAware_QuerySet
from input.models import CollectedInput

__all__ = ['CollectedInput_Postgres_JSON']


class CollectedInput_MySQL_JSON(CollectedInput):
    objects = JsonAware_QuerySet.as_manager()

    data = JSONField()
