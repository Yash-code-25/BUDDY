"""The employee portal: joiners and buddies sign in with their username and login code and see
everything about their buddy programme in one place."""
from django.conf import settings
from django.contrib.auth import logout
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response as ApiResponse
from rest_framework.views import APIView

from compass_app.clubs import INTERESTS, clubs_for, joiners_in_clubs_of
from compass_app.induction import current_pairing, progress
from compass_app.models import (
    AuditLog, Buddy, InductionItem, InductionTick, Joiner, Pairing, QuestionSet, Response, Settings,
)
from compass_app.views import current_response, status_of
from feedback.models import Feedback
from feedback.questions import QUESTIONS, SCALE, TITLE
from notifications import emails

from .auth import IsBuddy, IsJoiner, IsPortalPerson, PortalAuthentication, people_with_id, sign_in, sign_out

# What a joiner is told about where they are. Never scores, flags or admin notes.
JOINER_STAGE = {
    Joiner.Status.AWAITING_ASSESSMENT: "Answer the five questions so we can find your buddy.",
    Joiner.Status.AWAITING_PAIRING: "Thanks for your answers. We are choosing your buddy.",
    Joiner.Status.MANUAL: "Thanks. We are choosing your buddy.",
    Joiner.Status.ON_HOLD: "We are choosing your buddy.",
    Joiner.Status.PAIRED: "Your buddy is assigned. Follow your 4-week induction below.",
    Joiner.Status.CLOSED: "Your buddy programme has finished. Thank you!",
}


def interests_payload(person) -> dict:
    """The "What you enjoy outside work" card, for a joiner or a buddy."""
    return {"choices": INTERESTS, "selected": person.interests, "other": person.interests_other}
CONFIRM_FROM_DAYS = 3  # "Yes, I'll be there" shows from the logistics email, 3 days before joining


def review_payload(pairing) -> dict:
    opens_on = pairing.review_opens_on()
    return {
        "opens_on": opens_on,
        "open": timezone.localdate() >= opens_on,
        "submitted": hasattr(pairing, "review"),
        "title": TITLE,
        "questions": QUESTIONS,
        "scale": SCALE,
    }


def joiner_dashboard(joiner):
    today = timezone.localdate()
    quiz_status = status_of(current_response(joiner, Response.Code.JOINER, QuestionSet.active()))
    pairing = current_pairing(joiner)
    buddy = pairing.buddy if pairing else None
    settings_ = Settings.load()
    office = settings_.office_for(joiner.location)
    return {
        "date_of_joining": joiner.date_of_joining,
        "stage": JOINER_STAGE.get(joiner.compass_status, ""),
        "quiz": {
            "status": quiz_status,
            # Before day 1 and within a week of the "time to answer" email.
            "open": quiz_status != "submitted" and today <= joiner.date_of_joining
            and not joiner.quiz_link_expired(today),
            "link": f"/assess/joiner/{joiner.token}",
            # The day to answer by (the login email says the same), until they answer.
            "due": joiner.quiz_due(settings_.manual_cutoff_day) if quiz_status != "submitted" else None,
        },
        "buddy": {
            "name": buddy.name, "role": buddy.designation, "department": buddy.department,
            "location": buddy.location, "intro": buddy.intro,  # no email: joiners do not contact the buddy from here
            "start_date": pairing.start_date, "end_date": pairing.end_date,
        } if buddy else None,
        "induction": progress(joiner, pairing.start_date) if pairing else None,
        "review": review_payload(pairing) if pairing else None,
        "interests": interests_payload(joiner),
        "clubs": clubs_for(joiner),  # their interests at their location, with the buddies there
        "day_one": {
            # Shown from 3 days before joining until Day 1, or once they have confirmed.
            "show": 0 <= (joiner.date_of_joining - today).days <= CONFIRM_FROM_DAYS
            or joiner.attendance_confirmed_at is not None,
            "confirmed": joiner.attendance_confirmed_at is not None,
            "reporting_time": joiner.reporting_time, "office_address": office["address"],
            "map_link": office["map_link"], "contact_person": joiner.contact_person,
        },
    }


def buddy_dashboard(buddy):
    resp = current_response(buddy, Response.Code.BUDDY, QuestionSet.active())
    pairings = (
        Pairing.objects.filter(buddy=buddy, status=Pairing.Status.ACTIVE)
        .select_related("joiner").order_by("start_date")
    )
    return {
        "pool_status_label": buddy.get_pool_status_display(),
        "profile": {"status": status_of(resp), "link": f"/assess/buddy/{buddy.token}"},
        "joiners": [
            {
                "name": p.joiner.name, "role": p.joiner.designation, "department": p.joiner.department,
                "location": p.joiner.location, "date_of_joining": p.joiner.date_of_joining,
                "end_date": p.end_date, "induction": progress(p.joiner, p.start_date),
            }
            for p in pairings
        ],
        "total_joiners": buddy.total_joiners_buddied,
        "interests": interests_payload(buddy),
        "clubs": joiners_in_clubs_of(buddy),  # new joiners at their location who share their hobbies
    }


def me_payload(kind, person):
    data = {
        "kind": kind,
        "name": person.name,
        "first_name": emails.first_name(person.name),
        "username": person.candidate_id if kind == "joiner" else person.employee_id,
    }
    data.update(joiner_dashboard(person) if kind == "joiner" else buddy_dashboard(person))
    return data


class PortalView(APIView):
    authentication_classes = [PortalAuthentication]
    permission_classes = [IsPortalPerson]


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(PortalView):
    """GET: the signed-in person's page."""

    def get(self, request):
        return ApiResponse(me_payload(request.user.kind, request.user.person))


class LogoutView(PortalView):
    permission_classes = [AllowAny]

    def post(self, request):
        sign_out(request)
        return ApiResponse({"ok": True})


class InductionTickView(PortalView):
    """POST {done}: the joiner ticks (or unticks) one induction item."""
    permission_classes = [IsJoiner]

    def post(self, request, item_id):
        joiner = request.user.person
        pairing = current_pairing(joiner)
        if pairing is None:
            raise ValidationError("Your induction starts once your buddy is assigned.")
        try:
            item = InductionItem.objects.get(pk=item_id)
        except InductionItem.DoesNotExist:
            raise NotFound("That induction item no longer exists.")
        if request.data.get("done"):
            InductionTick.objects.get_or_create(joiner=joiner, item=item)
        else:
            InductionTick.objects.filter(joiner=joiner, item=item).delete()
        return ApiResponse(progress(joiner, pairing.start_date))


class ReviewView(PortalView):
    """POST {scores: [1-5, 1-5, 1-5], comment}: the joiner reviews their buddy after the 4 weeks."""
    permission_classes = [IsJoiner]

    def post(self, request):
        pairing = current_pairing(request.user.person)
        if pairing is None or not review_payload(pairing)["open"]:
            raise ValidationError("The buddy review opens after your 4-week induction.")
        scores = request.data.get("scores")
        valid = (
            isinstance(scores, list) and len(scores) == len(QUESTIONS)
            and all(isinstance(s, int) and not isinstance(s, bool) and 1 <= s <= 5 for s in scores)
        )
        if not valid:
            raise ValidationError("Please answer all three questions.")
        comment = str(request.data.get("comment", "")).strip()[:1000]
        try:
            with transaction.atomic():
                Feedback.objects.create(pairing=pairing, q1=scores[0], q2=scores[1], q3=scores[2], comment=comment)
        except IntegrityError:
            raise ValidationError("You have already reviewed your buddy. Thank you!")
        AuditLog.record("buddy_reviewed", pairing)
        return ApiResponse({"ok": True})


class RetakeProfileView(PortalView):
    """POST: the buddy reopens their finished profile to update it, with their answers filled in.
    Until they submit again they are left out of new matches (as when an admin asks them to)."""
    permission_classes = [IsBuddy]

    def post(self, request):
        buddy = request.user.person
        resp = current_response(buddy, Response.Code.BUDDY, QuestionSet.active())
        if status_of(resp) != "submitted":
            raise ValidationError("Your profile is not complete yet: finish it first.")
        resp.submitted_at = None
        resp.save(update_fields=["submitted_at"])
        AuditLog.record("profile_reopened", buddy)
        return ApiResponse({"link": f"/assess/buddy/{buddy.token}"})


class InterestsView(PortalView):
    """POST {selected: [...], other}: what the joiner or buddy enjoys outside work. Returns their
    interests and, for a joiner, their clubs."""

    def post(self, request):
        selected = request.data.get("selected")
        if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
            raise ValidationError("Please choose from the list.")
        unknown = [x for x in selected if x not in INTERESTS]
        if unknown:
            raise ValidationError(f"Not on the list: {', '.join(unknown)}.")
        person = request.user.person
        person.interests = [x for x in INTERESTS if x in selected]  # the list's order, once each
        person.interests_other = str(request.data.get("other", "")).strip()[:300]
        person.save(update_fields=["interests", "interests_other"])
        data = {"interests": interests_payload(person)}
        if request.user.kind == "joiner":
            data["clubs"] = clubs_for(person)
        return ApiResponse(data)


class AttendanceView(PortalView):
    """POST: "Yes, I'll be there" on Day 1."""
    permission_classes = [IsJoiner]

    def post(self, request):
        joiner = request.user.person
        if joiner.attendance_confirmed_at is None:
            joiner.attendance_confirmed_at = timezone.now()
            joiner.save(update_fields=["attendance_confirmed_at"])
            AuditLog.record("attendance_confirmed", joiner)
        return ApiResponse(joiner_dashboard(joiner)["day_one"])


class DemoSignInView(APIView):
    """Development only (settings.DEMO_SIGN_IN, which follows DEBUG): GET lists every joiner and buddy,
    POST {username} signs one in without their login code. Answers 404 when switched off."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def initial(self, request, *args, **kwargs):
        if not getattr(settings, "DEMO_SIGN_IN", False):
            raise Http404
        super().initial(request, *args, **kwargs)

    def get(self, request):
        joiners = [
            {"kind": "joiner", "username": j.candidate_id, "name": j.name,
             "detail": f"{j.department}, {j.location} · {j.get_compass_status_display()}"}
            for j in Joiner.objects.order_by("candidate_id")
        ]
        buddies = [
            {"kind": "buddy", "username": b.employee_id, "name": b.name,
             "detail": f"{b.department}, {b.location} · {b.active_joiners} joiner(s) now"}
            for b in Buddy.objects.exclude(pool_status=Buddy.PoolStatus.REMOVED).order_by("employee_id")
        ]
        return ApiResponse({"people": joiners + buddies})

    def post(self, request):
        found = people_with_id(str(request.data.get("username", "")))
        # A joiner and a buddy can share a username: the list says which one was clicked.
        wanted = request.data.get("kind")
        found = [(k, p) for k, p in found if k == wanted] or found
        if not found:
            raise ValidationError("No joiner or buddy with that username.")
        kind, person = found[0]
        logout(request._request)  # never signed in as an admin and an employee at once
        sign_in(request, kind, person)
        return ApiResponse({"to": "/portal"})
