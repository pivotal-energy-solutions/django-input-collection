from django_input_collection.compat import url, include

from . import views

urlpatterns = [
    url(r'^polls/', include([
        url(r'^(?P<pk>\d+)/', views.PollView.as_view()),
    ])),
]
