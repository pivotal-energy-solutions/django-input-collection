# -*- coding: utf-8 -*-
from django_input_collection import features

if features.rest_framework:
    from .poll import *
