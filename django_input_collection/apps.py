# -*- coding: utf-8 -*-
import logging
from django.apps import AppConfig, apps

import swapper
from django.conf import settings
from django.utils.functional import SimpleLazyObject

log = logging.getLogger(__name__)

swapper.set_app_prefix("django_input_collection", "input")

class InputConfig(AppConfig):
    name = "django_input_collection"
    verbose_name = "Input Collection"


class InputConfigApp:

    # Note this can be a callable to get data (print)
    VERBOSE_LOGGING = getattr(settings, "VERBOSE_INPUT_DEBUGGING", False)

    @classmethod
    def get_config(cls):
        """Returns an importable lazy wrapper for the appconfig of an app by its name."""
        return SimpleLazyObject(lambda: apps.get_app_config(cls.app_name()))

    @classmethod
    def app_name(cls):
        """Return app name without a package prefix."""
        return cls.name.split(".", 1)[-1]

    @property
    def get_verbose_logging(self) -> tuple:
        _should_log = self.VERBOSE_LOGGING
        log_method = log.debug
        if not isinstance(_should_log, bool) and callable(_should_log):
            log_method = _should_log
            should_log = True
        return (should_log, log_method)


app = SimpleLazyObject(InputConfigApp)
