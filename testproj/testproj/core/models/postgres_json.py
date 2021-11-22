# -*- coding: utf-8 -*-
from django.contrib.postgres.fields import JSONField

from django_input_collection.models import AbstractCollectedInput

__all__ = ["CollectedInput_Postgres_JSON"]


class CollectedInput_Postgres_JSON(AbstractCollectedInput):
    data = JSONField()
