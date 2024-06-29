# -*- coding: utf-8 -*-
from django.conf import settings

from .base import *  # noqa: F403

if settings.INPUT_COLLECTEDINPUT_MODEL == "core.CollectedInput_MySQL_JSON":
    from .mysql_json import *  # noqa: F403
elif settings.INPUT_COLLECTEDINPUT_MODEL == "core.CollectedInput_Postgres_JSON":
    from .mysql_postgres import *  # noqa: F403
