from django.db import models

from input.models import CollectedInput

__all__ = ['CollectedInput_Postgres_JSON']


class CollectedInput_Postgres_JSON(CollectedInput):
    data = models.JSONField()
