from .dev import *

# MySQL mode
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'input_testproj',
    'USERNAME': env.get_variable('DATABASE_USERNAME', 'root'),
    'PASSWORD': env.get_variable('DATABASE_PASSWORD', ''),
}
INSTALLED_APPS.extend([
    'django_mysql',
])
INPUT_COLLECTEDINPUT_MODEL = 'testproj.CollectedInput_MySQL_JSON'


# Postgres mode
# DATABASES['default'] = {
#     'ENGINE': 'django.db.backends.postgres',
#     'NAME': 'input_testproj',
#     'USERNAME': env.get_variable('DATABASE_USERNAME', 'root'),
#     'PASSWORD': env.get_variable('DATABASE_PASSWORD', ''),
# }
# INPUT_COLLECTEDINPUT_MODEL = 'testproj.CollectedInput_Postgres_JSON'