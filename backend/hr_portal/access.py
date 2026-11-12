"""Who may use the admin screens. COMPASS has one staff role, the Program admin: any active staff
user. The superuser (the developer) has the same powers in COMPASS and is the only one who can add
Program admins, in the Django admin at /admin."""
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView


class IsProgramAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class AdminView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsProgramAdmin]
