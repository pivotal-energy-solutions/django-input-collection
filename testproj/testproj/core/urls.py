from django_input_collection import features
from django_input_collection.compat import url, include

from . import views

urlpatterns = []
if features.rest_framework:
    urlpatterns.extend([
        url(r'^polls/', include([
            url(r'^(?P<pk>\d+)/', views.PollView.as_view()),
        ])),
    ]
