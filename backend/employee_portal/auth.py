"""Who is signed in to the employee portal.

Joiners and buddies are not Django users (those are the Program admins). The session remembers
which joiner or buddy it is, and every change they make is CSRF-checked, the same as for admins."""
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission

from compass_app.models import Buddy, Joiner

SESSION_KEY = "portal"
MODELS = {"joiner": Joiner, "buddy": Buddy}


class PortalPerson:
    """request.user for a signed-in joiner or buddy."""
    is_authenticated = True

    def __init__(self, kind, person):
        self.kind = kind
        self.person = person


def can_sign_in(kind, person) -> bool:
    return not (kind == "buddy" and person.pool_status == Buddy.PoolStatus.REMOVED)


def people_with_id(login_id: str):
    """Everyone who signs in with this username: a buddy's employee id or a joiner's candidate id."""
    login_id = login_id.strip()
    if not login_id:
        return []
    found = [("buddy", Buddy.objects.filter(employee_id__iexact=login_id).first()),
             ("joiner", Joiner.objects.filter(candidate_id__iexact=login_id).first())]
    return [(kind, person) for kind, person in found if person and can_sign_in(kind, person)]


def sign_in(request, kind, person):
    """Remember this person in the session. A new session key stops session fixation."""
    request.session.cycle_key()
    request.session[SESSION_KEY] = {"kind": kind, "id": person.pk}


def sign_out(request):
    request.session.pop(SESSION_KEY, None)


def signed_in(request):
    """(kind, person) for the session, or None."""
    data = request.session.get(SESSION_KEY)
    model = MODELS.get((data or {}).get("kind"))
    if model is None:
        return None
    person = model.objects.filter(pk=data.get("id")).first()
    if person is None or not can_sign_in(data["kind"], person):
        return None
    return data["kind"], person


class PortalAuthentication(SessionAuthentication):
    def authenticate(self, request):
        found = signed_in(request._request)
        if found is None:
            return None
        self.enforce_csrf(request)
        return PortalPerson(*found), None


class IsPortalPerson(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, PortalPerson)


class IsBuddy(IsPortalPerson):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.kind == "buddy"


class IsJoiner(IsPortalPerson):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.kind == "joiner"
