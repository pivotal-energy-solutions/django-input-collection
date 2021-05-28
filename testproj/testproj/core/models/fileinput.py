from django.db import models
from django.conf import settings

__all__ = ["CollectedFileInput"]


class CollectedFileInput(models.Model):

    # If only one file should be allowed to be provided for an Input, you can still allow multiple
    # files by associating each one to its own parent CollectedInput, where every 'data' attribute
    # up there is something like a file handle.
    input = models.OneToOneField(settings.INPUT_COLLECTEDINPUT_MODEL, on_delete=models.CASCADE)

    # Using a ForeignKey instead, you can relate multiple files to one CollectedInput, and you
    # could still track quick file handles in the parent instance using a more intricate field,
    # like a long TextField with separators, or a JSONField for your database backend where a list
    # of them can be stored.  We might therefore expect to have to swap out CollectedInput for a
    # customized version to support our strategy.
    # input = models.ForeignKey(settings.INPUT_COLLECTEDINPUT_MODEL, on_delete=models.CASCADE)

    file = models.FileField(upload_to="file-inputs/")
