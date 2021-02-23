from django_input_collection import features
from django.urls import re_path, include

from . import views

urlpatterns = []

if features.rest_framework:
    urlpatterns.extend([
        re_path(r'^polls/', include([
            re_path(r'^(?P<pk>\d+)/', views.PollView.as_view()),
        ])),
    ])
