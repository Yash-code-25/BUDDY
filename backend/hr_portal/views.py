import logging
import re
from datetime import date

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response as ApiResponse
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from compass_app.induction import current_pairing, progress
from compass_app.models import AuditLog, Buddy, Joiner, MatchRun, Pairing, Settings
from employee_portal import auth as portal
from employee_portal.credentials import issue_login
from notifications import emails

from . import people
from .access import AdminView

logger = logging.getLogger(__name__)

REASONS = [
    "Buddy capacity", "Language or shift fit", "Manager request", "Prior relationship", "Other",
]


def user_payload(user):
    return {"username": user.username, "name": user.get_full_name() or user.username}


def multi(request, key) -> list:
    return [v for v in request.query_params.get(key, "").split(",") if v]


# ---------- sign in / out ----------

class LoginView(APIView):
    """POST {username, password}: the one sign-in for everyone. Program admins use their username
    and password; joiners and buddies their candidate or employee id and login code. The reply
    says where to go next."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", "")).strip()
        user = authenticate(request._request, username=username, password=password)
        if user is not None and user.is_staff:
            portal.sign_out(request)
            login(request._request, user)
            return ApiResponse({**user_payload(user), "to": "/hr"})
        for kind, person in portal.people_with_id(username):
            if person.check_login_code(password):
                logout(request._request)  # never signed in as an admin and an employee at once
                portal.sign_in(request, kind, person)
                return ApiResponse({"kind": kind, "name": person.name, "to": "/portal"})
        raise ValidationError("Wrong username, password or login code.")


class LogoutView(AdminView):
    def post(self, request):
        logout(request._request)
        return ApiResponse({"ok": True})


class MeView(AdminView):
    def get(self, request):
        return ApiResponse(user_payload(request.user))


# ---------- helpers ----------

def latest_run(joiner):
    return MatchRun.objects.filter(joiner=joiner).order_by("-run_time").first()


def open_pairing(joiner):
    return Pairing.objects.filter(joiner=joiner, status=Pairing.Status.ACTIVE).select_related("buddy").first()


JOINER_FIELDS = [
    "candidate_id", "name", "personal_email", "department", "location", "brand", "function", "designation",
    "designation_track", "reporting_manager_id", "date_of_joining", *people.DAY_ONE,
    "attendance_confirmed_at",
]


# One note per line: "[2026-11-05 14:30 Admin] text". Older notes have no time and the admin's username.
NOTE_LINE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?[^\]]*\] ?(.*)$")


def note_entries(notes: str) -> list:
    """The joiner's notes, newest first. Every note is by a Program admin, so the screen shows "Admin"
    (the audit log keeps who it was). A line that does not start a note continues the one before."""
    entries = []
    for line in notes.splitlines():
        match = NOTE_LINE.match(line)
        if match:
            entries.append({"date": match[1], "time": match[2] or "", "text": match[3]})
        elif entries:
            entries[-1]["text"] += "\n" + line
        elif line.strip():
            entries.append({"date": "", "time": "", "text": line})
    return entries[::-1]


def joiner_payload(joiner, today):
    return {
        "id": joiner.pk,
        **{f: getattr(joiner, f) for f in JOINER_FIELDS},
        "days_to_joining": (joiner.date_of_joining - today).days,
        "status": joiner.compass_status,
        "status_label": joiner.get_compass_status_display(),
        "notes": note_entries(joiner.notes),
    }


def filter_people(request, queryset, status_field):
    """The filters joiners and buddies share: department, location, brand, status and name."""
    for field, values in (("department", multi(request, "department")), ("location", multi(request, "location")),
                          ("brand", multi(request, "brand")), (status_field, multi(request, "status"))):
        if values:
            queryset = queryset.filter(**{f"{field}__in": values})
    if request.query_params.get("q"):
        queryset = queryset.filter(name__icontains=request.query_params["q"])
    return queryset


def filter_joiners(request, queryset):
    q = request.query_params
    queryset = filter_people(request, queryset, "compass_status")
    for key, lookup in (("doj_from", "gte"), ("doj_to", "lte")):
        if q.get(key):
            try:
                day = date.fromisoformat(q[key])
            except ValueError:
                raise ValidationError(f"{key} must look like 2026-11-09.")
            queryset = queryset.filter(**{f"date_of_joining__{lookup}": day})
    return queryset


# ---------- queue, add, import ----------

class JoinerQueueView(AdminView):
    def get(self, request):
        today = timezone.localdate()
        joiners = filter_joiners(request, Joiner.objects.all()).order_by("date_of_joining", "name")
        # Only the top suggestion of each joiner's latest run: a whole run lists every buddy scored,
        # which is slow to load for hundreds of joiners.
        runs = {}
        for run in (MatchRun.objects.filter(joiner__in=joiners).order_by("run_time")
                    .values("joiner_id", "tier_reached", "results__shown__0")):
            runs[run["joiner_id"]] = run

        bands, tiers = multi(request, "band"), multi(request, "tier")
        rows = []
        for joiner in joiners:
            run = runs.get(joiner.pk)
            top = run["results__shown__0"] if run else None
            row = {
                **joiner_payload(joiner, today),
                "tier_reached": run["tier_reached"] if run else "",
                "best_band": top["band"] if top else "",
                "flags_count": len(top["flags"]) if top else 0,
            }
            band_value = row["best_band"] or ("Manual" if run else "")
            if bands and band_value not in bands:
                continue
            if tiers and row["tier_reached"] not in tiers:
                continue
            rows.append(row)
        return ApiResponse(rows)

    def post(self, request):
        """Add a joiner. They are emailed their username and login code straight away."""
        joiner = people.create_person(request.data, request.user, people.JOINERS, "joiner_created")
        return ApiResponse({"id": joiner.pk}, status=201)


class CsvImportView(AdminView):
    """POST {csv}: the joiners or buddies in a CSV file (the stand-in for the HRMS feed)."""
    importer = None

    def post(self, request):
        text = request.data.get("csv", "")
        if not str(text).strip():
            raise ValidationError("The file is empty.")
        return ApiResponse(self.importer(str(text), request.user))


class JoinerImportView(CsvImportView):
    importer = staticmethod(people.import_joiners)


# ---------- one joiner ----------

def pairing_payload(pairing):
    return {
        "id": pairing.pk,
        "buddy_pk": pairing.buddy.pk,
        "buddy_id": pairing.buddy.employee_id,
        "buddy_name": pairing.buddy.name,
        "status": pairing.status,
        "source": pairing.source,
        "band": pairing.band,
        "override_reason": pairing.override_reason,
        "assigned_at": pairing.assigned_at,
        "start_date": pairing.start_date,
        "end_date": pairing.end_date,
        "can_change": pairing.can_change(),
        "review_opens_on": pairing.review_opens_on(),
        "reviewed": hasattr(pairing, "review"),
    }


class JoinerDetailView(AdminView):
    def get(self, request, pk):
        joiner = get_object_or_404(Joiner, pk=pk)
        resp = joiner.submitted_response()
        questions, answers = [], []
        if resp:
            qs = list(resp.question_set.questions.all())
            # every label, so the screen can show each candidate buddy's answers in words
            questions = [q.payload() for q in qs]
            answers = [
                {"number": q.number, "dimension": q.dimension, "text": q.text, "value": value, "label": q.label(value)}
                for q, value in zip(qs, resp.answers())
            ]

        run = latest_run(joiner)
        pairing = current_pairing(joiner)
        s = Settings.load()
        return ApiResponse({
            "joiner": joiner_payload(joiner, timezone.localdate()),
            "questions": questions,
            "answers": answers,
            "run": {"id": run.pk, "run_time": run.run_time, **run.results} if run else None,
            "pairing": pairing_payload(pairing) if pairing else None,
            "induction": progress(joiner, pairing.start_date) if pairing else None,
            "reasons": REASONS,
            "settings": {"candidates_per_tier": s.candidates_per_tier, "close_gap": s.close_gap},
        })


class JoinerActionView(AdminView):
    """Quick actions on one joiner: remind, route to manual, hold, release, not required, note,
    send login details."""

    def post(self, request, pk):
        joiner = get_object_or_404(Joiner, pk=pk)
        action = request.data.get("action")
        note = str(request.data.get("note", "")).strip()
        status = joiner.compass_status
        S = Joiner.Status
        before = status
        stamp = emails.stamp()

        def append_note(text):
            line = f"[{timezone.localtime():%Y-%m-%d %H:%M} Admin] {text}"
            joiner.notes = f"{joiner.notes}\n{line}".strip()

        if action == "remind":
            if joiner.submitted_response():
                raise ValidationError("This joiner has already submitted their answers.")
            emails.send_joiner_reminder(joiner, f"manual-{stamp}")
            joiner.quiz_link_sent_on = timezone.localdate()  # a reminder opens a fresh week
        elif action == "manual":
            if status not in (S.AWAITING_ASSESSMENT, S.AWAITING_PAIRING, S.ON_HOLD):
                raise ValidationError("This joiner cannot be routed to manual pairing now.")
            joiner.compass_status = S.MANUAL
        elif action == "hold":
            if status not in (S.AWAITING_ASSESSMENT, S.AWAITING_PAIRING, S.MANUAL):
                raise ValidationError("This joiner cannot be put on hold now.")
            joiner.compass_status = S.ON_HOLD
        elif action == "release":
            if status != S.ON_HOLD:
                raise ValidationError("This joiner is not on hold.")
            joiner.compass_status = (
                S.AWAITING_PAIRING if joiner.submitted_response() else S.AWAITING_ASSESSMENT
            )
        elif action == "not_required":
            if open_pairing(joiner):
                raise ValidationError("This joiner already has a buddy.")
            joiner.compass_status = S.CLOSED
            append_note(f"Buddy not required. {note}".strip())
        elif action == "note":
            if not note:
                raise ValidationError("Please write a note.")
            append_note(note)
        elif action == "send_login":
            if not issue_login(joiner, "joiner"):
                raise ValidationError("Could not email the login details. Check the joiner's email address.")
        else:
            raise ValidationError("Unknown action.")

        joiner.save(update_fields=["compass_status", "notes", "quiz_link_sent_on"])
        AuditLog.record(f"joiner_{action}", joiner, user=request.user,
                        before={"status": before}, after={"status": joiner.compass_status, "note": note})
        return ApiResponse({"status": joiner.compass_status})


class JoinerDayOneView(AdminView):
    """PUT the joiner's Day 1 details (manager, reporting time, address…) for the pre-joining emails."""

    def put(self, request, pk):
        joiner = get_object_or_404(Joiner, pk=pk)
        before = {f: getattr(joiner, f) for f in people.DAY_ONE}
        after = {}
        for field in people.DAY_ONE:
            value = str(request.data.get(field, before[field]) or "").strip()
            limit = Joiner._meta.get_field(field).max_length
            if len(value) > limit:
                raise ValidationError(f"{field.replace('_', ' ').capitalize()} can be at most {limit} characters.")
            after[field] = value
            setattr(joiner, field, value)
        joiner.save(update_fields=people.DAY_ONE)
        changed = {k: v for k, v in after.items() if before[k] != v}
        if changed:
            AuditLog.record("joiner_day_one_changed", joiner, user=request.user,
                            before={k: before[k] for k in changed}, after=changed)
        return ApiResponse(joiner_payload(joiner, timezone.localdate()))


class AssignBuddyView(AdminView):
    """POST {buddy_id, reason?, note?}: assign a buddy. The pairing is active at once and both
    people are emailed. Within 2 days of assigning, the same call changes the buddy."""

    def post(self, request, pk):
        joiner = get_object_or_404(Joiner, pk=pk)
        buddy_id = str(request.data.get("buddy_id", "")).strip()
        reason = str(request.data.get("reason", "")).strip()
        note = str(request.data.get("note", "")).strip()

        run = latest_run(joiner)
        if run is None:
            raise ValidationError("There is no match run for this joiner yet.")
        results = run.results
        chosen = {c["buddy_id"]: c for c in results["scored"]}.get(buddy_id)
        if chosen is None:
            raise ValidationError("That buddy is not eligible for this joiner.")
        buddy = get_object_or_404(Buddy, employee_id=buddy_id)
        if buddy.pool_status != Buddy.PoolStatus.ACTIVE:
            raise ValidationError("That buddy is not active in the pool. Re-run the match.")

        suggested = {c["buddy_id"] for tier in results["tiers"].values() for c in tier}
        suggested |= {c["buddy_id"] for c in results["weaker"]}
        top_id = results["shown"][0]["buddy_id"] if results["shown"] else None
        if buddy_id == top_id:
            source = Pairing.Source.SYSTEM
        elif buddy_id in suggested:
            source = Pairing.Source.SYSTEM_OVERRIDE
        else:
            source = Pairing.Source.MANUAL

        has_red = any(f["level"] == "Red" for f in chosen["flags"])
        override_reason = ""
        if source != Pairing.Source.SYSTEM or chosen["band"] == "Weaker" or has_red:
            if reason not in REASONS:
                raise ValidationError("Please choose a reason for this choice.")
            if reason == "Other" and not note:
                raise ValidationError("Please add a note when the reason is Other.")
            override_reason = f"{reason}: {note}" if note else reason

        with transaction.atomic():
            joiner = Joiner.objects.select_for_update().get(pk=joiner.pk)
            old = open_pairing(joiner)
            if old is None and joiner.compass_status not in (Joiner.Status.AWAITING_PAIRING, Joiner.Status.MANUAL):
                raise ValidationError("This joiner is not waiting for a buddy.")
            if old is not None:
                if not old.can_change():
                    raise ValidationError("The buddy can only be changed within 2 days of assigning.")
                if old.buddy_id == buddy.pk:
                    raise ValidationError(f"{buddy.name} is already this joiner's buddy.")
                old.status = Pairing.Status.CANCELLED
                old.save(update_fields=["status"])
                Buddy.objects.filter(pk=old.buddy_id).update(
                    active_joiners=F("active_joiners") - 1, total_joiners_buddied=F("total_joiners_buddied") - 1,
                )
            start, end = Pairing.dates_for(joiner)
            pairing = Pairing.objects.create(
                joiner=joiner, buddy=buddy, source=source,
                system_top_pick=Buddy.objects.filter(employee_id=top_id).first() if top_id else None,
                band=chosen["band"], flags=chosen["flags"], close_count=chosen["close_count"],
                override_reason=override_reason, assigned_by=request.user, start_date=start, end_date=end,
            )
            Buddy.objects.filter(pk=buddy.pk).update(
                active_joiners=F("active_joiners") + 1, total_joiners_buddied=F("total_joiners_buddied") + 1,
            )
            before = joiner.compass_status
            joiner.compass_status = Joiner.Status.PAIRED
            joiner.save(update_fields=["compass_status"])
            AuditLog.record(
                "buddy_changed" if old else "buddy_assigned", joiner, user=request.user,
                before={"status": before, "buddy": old.buddy.employee_id if old else None},
                after={"pairing_id": pairing.pk, "buddy": buddy_id, "source": source, "reason": override_reason},
            )

        # The pairing is saved, so an email problem must not undo it.
        try:
            if old:
                emails.send_assignment_removed(old)
            emails.send_assignment(pairing)
        except Exception:
            logger.exception("Could not email the assignment for pairing %s", pairing.pk)
        return ApiResponse({"pairing_id": pairing.pk, "source": source})
