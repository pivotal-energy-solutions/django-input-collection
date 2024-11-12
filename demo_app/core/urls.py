from django_input_collection import features
from django.urls import path, include

from . import views

urlpatterns = []

if features.rest_framework:
    urlpatterns.extend(
        [
            path(
                "polls/",
                include(
                    [
                        path("<int:pk>/", views.PollView.as_view()),
                    ]
                ),
            ),
        ]
    )
