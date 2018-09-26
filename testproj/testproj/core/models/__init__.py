from django.conf import settings

from .base import *

if settings.INPUT_COLLECTEDINPUT_MODEL == 'core.CollectedInput_MySQL_JSON':
    from .mysql_json import *
elif settings.INPUT_COLLECTEDINPUT_MODEL == 'core.CollectedInput_Postgres_JSON':
    from .mysql_postgres import *
