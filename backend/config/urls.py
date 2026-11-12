"""
URL configuration for config project.

Django's own addresses come first (admin and the API). Anything else is a page of the React app,
which config.frontend serves from frontend/dist.
"""
from django.contrib import admin
from django.urls import include, path, re_path

from employee_portal.views import DemoSignInView
from hr_portal.views import LoginView

from .frontend import frontend

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', LoginView.as_view()),  # Program admins, joiners and buddies
    path('api/auth/demo/', DemoSignInView.as_view()),  # development only
    path('api/hr/', include('hr_portal.urls')),
    path('api/portal/', include('employee_portal.urls')),
    path('api/', include('compass_app.urls')),
    re_path(r'^(?P<path>.*)$', frontend),
]
