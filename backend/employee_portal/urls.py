from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MeView.as_view()),
    path("logout/", views.LogoutView.as_view()),
    path("induction/<int:item_id>/", views.InductionTickView.as_view()),
    path("review/", views.ReviewView.as_view()),
    path("interests/", views.InterestsView.as_view()),
    path("retake/", views.RetakeProfileView.as_view()),
    path("attendance/", views.AttendanceView.as_view()),
]
