from django.db import models

import swapper

__all__ = ['get_input_model']

def get_input_model():
    return swapper.load_model('input', 'CollectedInput')


class DatesMixin(object):
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
