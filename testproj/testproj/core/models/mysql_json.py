from django_mysql.models import JSONField
from django_input_collection.models import AbstractCollectedInput

from .managers import JSONUserLatestCollectedInputQuerySet

__all__ = ["CollectedInput_MySQL_JSON"]


class CollectedInput_MySQL_JSON(AbstractCollectedInput):
    objects = JSONUserLatestCollectedInputQuerySet.as_manager()

    data = JSONField()
