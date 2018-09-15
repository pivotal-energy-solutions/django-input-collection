from django.urls import path, include

from . import views

urlpatterns = [
    path('polls/', include([
        path('<pk>/', views.PollView.as_view()),
    ])),
]
