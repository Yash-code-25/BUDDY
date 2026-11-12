from django.urls import path

from . import views

urlpatterns = [
    path("assessment/<str:kind>/<uuid:token>/", views.AssessmentView.as_view()),
    path("assessment/<str:kind>/<uuid:token>/answer/", views.AnswerView.as_view()),
    path("assessment/<str:kind>/<uuid:token>/submit/", views.SubmitView.as_view()),
]