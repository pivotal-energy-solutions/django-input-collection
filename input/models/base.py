from django.db import models

__all__ = ['Measure']


class Measure(models.Model):
    """
    A deployed question's underlying identity, regardless of phrasing or possible answer choices.
    Models that collect for a Measure use a ForeignKey pointing to the appropriate Measure.
    """
    id = models.CharField(max_length=100, primary_key=True)

    def __str__(self):
        return self.id
