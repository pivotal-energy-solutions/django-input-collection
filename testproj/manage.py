#!/usr/bin/env python
import os
import sys

# current_path = os.path.abspath('.')
# if current_path.endswith(os.path.sep + 'django-input-collection'):
#     sys.path.insert(0, 'testproj')

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testproj.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        )
    execute_from_command_line(sys.argv)
