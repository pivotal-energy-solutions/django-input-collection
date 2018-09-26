from input.models.managers import UserLatestCollectedInputQuerySet
from django_mysql.models import QuerySetMixin as JSONQuerySetMixin


class JSONUserLatestCollectedInputQuerySet(JSONQuerySetMixin, UserLatestCollectedInputQuerySet):
    pass
