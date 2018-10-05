from .dev import *

INSTALLED_APPS.extend([
    'rest_framework',
])

# Default mode
INPUT_COLLECTEDINPUT_MODEL = 'django_input_collection.CollectedInput'

# MySQL mode
# DATABASES['default'] = {
#     'ENGINE': 'django.db.backends.mysql',
#     'NAME': 'input_testproj',
#     'USER': env.get_variable('DATABASE_USERNAME', 'root'),
#     'PASSWORD': env.get_variable('DATABASE_PASSWORD', ''),
# }
# INSTALLED_APPS.extend([
#     'django_mysql',
# ])
# INPUT_COLLECTEDINPUT_MODEL = 'core.CollectedInput_MySQL_JSON'


# Postgres mode
# DATABASES['default'] = {
#     'ENGINE': 'django.db.backends.postgres',
#     'NAME': 'input_testproj',
#     'USERNAME': env.get_variable('DATABASE_USERNAME', 'root'),
#     'PASSWORD': env.get_variable('DATABASE_PASSWORD', ''),
# }
# INPUT_COLLECTEDINPUT_MODEL = 'testproj.CollectedInput_Postgres_JSON'


import sys
if sys.argv[1] == 'test':
    from .test import *
