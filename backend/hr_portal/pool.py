"""The buddy pool: list, add, edit, import, and the per-buddy actions."""
from collections import defaultdict

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response as ApiResponse

from compass_app.models import AuditLog, Buddy, Pairing, QuestionSet, Response
from employee_portal.credentials import issue_login
from notifications import emails

from . import people
from .access import AdminView
from .views import CsvImportView, filter_people, multi

EDITABLE = ["name", "email", "department", "location", "brand", "designation", "intro"]


def profile_responses(question_set=None):
    """buddy pk -> their CMP-BD response on the active question set."""
    question_set = question_set or QuestionSet.active()
    return {
        r.buddy_id: r
        for r in Response.objects.filter(assessment_code=Response.Code.BUDDY, question_set=question_set)
    }


def cmpbd_status(resp) -> str:
    if resp is None or all(a is None for a in resp.answers()):
        return "not_started"
    return "completed" if resp.submitted_at else "in_progress"


def count_without_profile() -> int:
    """Buddies still in the pool (not removed) who have not finished their profile."""
    responses = profile_responses()
    return sum(1 for b in Buddy.objects.exclude(pool_status=Buddy.PoolStatus.REMOVED)
               if cmpbd_status(responses.get(b.pk)) != "completed")


def buddy_row(buddy, resp):
    return {
        "id": buddy.pk,
        "employee_id": buddy.employee_id,
        **{f: getattr(buddy, f) for f in EDITABLE},
        "pool_status": buddy.pool_status,
        "pool_status_label": buddy.get_pool_status_display(),
        "cmpbd_status": cmpbd_status(resp),
        "total_joiners": buddy.total_joiners_buddied,
        "active_joiners": buddy.active_joiners,
        "date_added": buddy.date_added_to_pool,
    }


class BuddyListView(AdminView):
    def get(self, request):
        return ApiResponse(self.rows(request))

    @staticmethod
    def rows(request) -> list:
        """The buddies, narrowed by the filters in the address."""
        buddies = filter_people(request, Buddy.objects.order_by("name"), "pool_status")
        responses = profile_responses()
        wanted_status = multi(request, "cmpbd")
        # q1=5 or q4=1,2: buddies who gave one of those answers to that question
        wanted_answers = {n: [int(v) for v in multi(request, f"q{n}") if v.isdigit()] for n in range(1, 6)}

        def wanted(buddy):
            resp = responses.get(buddy.pk)
            return all(not values or (resp is not None and resp.answers()[n - 1] in values)
                       for n, values in wanted_answers.items())

        rows = [buddy_row(b, responses.get(b.pk)) for b in buddies if wanted(b)]
        return [r for r in rows if not wanted_status or r["cmpbd_status"] in wanted_status]

    def post(self, request):
        buddy = people.create_person(request.data, request.user, people.BUDDIES, "buddy_added")
        return ApiResponse({"id": buddy.pk}, status=201)


class BuddyGroupsView(AdminView):
    """The same buddies as the list, laid out as groups (department and location). Under each buddy
    are the joiners they look after right now. Every joiner still has exactly one buddy."""

    def get(self, request):
        rows = BuddyListView.rows(request)
        looking_after = defaultdict(list)
        pairings = (
            Pairing.objects.filter(
                buddy_id__in=[r["id"] for r in rows], status=Pairing.Status.ACTIVE,
            )
            .select_related("joiner")
            .order_by("joiner__date_of_joining", "joiner__name")
        )
        for p in pairings:
            looking_after[p.buddy_id].append({
                "joiner_id": p.joiner_id,
                "name": p.joiner.name,
                "date_of_joining": p.joiner.date_of_joining,
                "end_date": p.end_date,
            })

        groups = defaultdict(list)
        for row in rows:
            groups[(row["department"], row["location"])].append({**row, "joiners": looking_after[row["id"]]})

        return ApiResponse([
            {
                "department": department,
                "location": location,
                "buddies": buddies,
                "active_joiners": sum(b["active_joiners"] for b in buddies),
            }
            for (department, location), buddies in sorted(groups.items())
        ])


class BuddyImportView(CsvImportView):
    importer = staticmethod(people.import_buddies)


class BuddyDetailView(AdminView):
    def get(self, request, pk):
        buddy = get_object_or_404(Buddy, pk=pk)
        resp = profile_responses().get(buddy.pk)
        answers = []
        if resp and resp.submitted_at:
            for q, value in zip(resp.question_set.questions.all(), resp.answers()):
                answers.append({
                    "number": q.number, "dimension": q.dimension, "value": value,
                    "label": q.label(value),
                })
        history = [
            {
                "joiner": p.joiner.name, "joiner_id": p.joiner_id, "status": p.status,
                "band": p.band, "source": p.source,
                "assigned_at": p.assigned_at, "start_date": p.start_date, "end_date": p.end_date,
            }
            for p in buddy.pairings.select_related("joiner").order_by("-assigned_at")
        ]
        return ApiResponse({
            **buddy_row(buddy, resp),
            "answers": answers,
            "version": resp.question_set.version if resp else None,
            "submitted_at": resp.submitted_at if resp else None,
            "history": history,
        })

    def patch(self, request, pk):
        buddy = get_object_or_404(Buddy, pk=pk)
        row = {"employee_id": buddy.employee_id, **{f: getattr(buddy, f) for f in EDITABLE}}
        before = dict(row)
        row.update({k: v for k, v in request.data.items() if k in EDITABLE})
        try:
            _, data = people.clean_buddy(row)
        except people.RowError as e:
            raise ValidationError(str(e))
        data.setdefault("intro", "")
        for field, value in data.items():
            if field != "total_joiners_buddied":
                setattr(buddy, field, value)
        buddy.save()
        AuditLog.record("buddy_edited", buddy, user=request.user, before=before, after=row)
        return ApiResponse({"ok": True})


class BuddyActionView(AdminView):
    """pause, resume, leave, remove, remind, send_login, retake, reset."""

    def post(self, request, pk):
        buddy = get_object_or_404(Buddy, pk=pk)
        action = request.data.get("action")
        P = Buddy.PoolStatus
        resp = profile_responses().get(buddy.pk)
        before = buddy.pool_status
        stamp = emails.stamp()

        if action == "pause":
            buddy.pool_status = P.PAUSED
        elif action == "leave":
            buddy.pool_status = P.ON_LEAVE
        elif action == "remove":
            buddy.pool_status = P.REMOVED
        elif action == "resume":
            if cmpbd_status(resp) != "completed":
                raise ValidationError("This buddy has not completed their profile yet.")
            buddy.pool_status = P.ACTIVE
        elif action == "remind":
            if cmpbd_status(resp) == "completed":
                raise ValidationError("This buddy has already completed their profile.")
            emails.send_buddy_reminder(buddy, f"manual-{stamp}")
        elif action == "send_login":
            if not issue_login(buddy, "buddy"):
                raise ValidationError("Could not email the login details. Check the buddy's email address.")
        elif action == "retake":
            if cmpbd_status(resp) != "completed":
                raise ValidationError("This buddy has not completed their profile yet.")
            # Reopened with the old answers filled in. Until the buddy submits again they are left
            # out of new matches; submitting puts them back.
            resp.submitted_at = None
            resp.save(update_fields=["submitted_at"])
            emails.send_buddy_retake(buddy, stamp)
        elif action == "reset":
            if resp is None:
                raise ValidationError("There is nothing to reset.")
            AuditLog.record("response_reset", buddy, user=request.user, before={"answers": resp.answers()})
            resp.delete()
            buddy.pool_status = P.PAUSED
        else:
            raise ValidationError("Unknown action.")

        buddy.save(update_fields=["pool_status"])
        AuditLog.record(f"buddy_{action}", buddy, user=request.user,
                        before={"pool_status": before}, after={"pool_status": buddy.pool_status})
        return ApiResponse({"pool_status": buddy.pool_status})
