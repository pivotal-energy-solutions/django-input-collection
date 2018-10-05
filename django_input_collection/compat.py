try:
    from django.urls import url, include
except ImportError:
    from django.conf.urls import url, include

try:
    from collections import UserDict
except ImportError:
    from UserDict import IterableUserDict as UserDict
