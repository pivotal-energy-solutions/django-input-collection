from django.apps import AppConfig

import swapper

swapper.set_app_prefix('django_input_collection', 'input')


class InputConfig(AppConfig):
    name = 'django_input_collection'
    verbose_name = 'Input Collection'
