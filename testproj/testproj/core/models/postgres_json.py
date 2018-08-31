from django.contrib.postgres.fields import JSONField

from input.models import AbstractCollectedInput

__all__ = ['CollectedInput_Postgres_JSON']


class CollectedInput_Postgres_JSON(AbstractCollectedInput):
    data = JSONField()
