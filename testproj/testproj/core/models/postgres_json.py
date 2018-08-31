from django.contrib.postgres.fields import JSONField

from input.models import CollectedInput

__all__ = ['CollectedInput_Postgres_JSON']


class CollectedInput_Postgres_JSON(CollectedInput):
    data = JSONField()
