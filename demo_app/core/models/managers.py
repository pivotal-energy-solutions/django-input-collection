# -*- coding: utf-8 -*-
from django_input_collection.models.managers import UserLatestCollectedInputQuerySet
from django_mysql.models import QuerySetMixin as JSONQuerySetMixin


class JSONUserLatestCollectedInputQuerySet(JSONQuerySetMixin, UserLatestCollectedInputQuerySet):
    pass
