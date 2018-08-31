from django.db import models

from input.models import CollectedInput


class CollectedInput_Postgres_JSON(CollectedInput):
    data = models.JSONField()
