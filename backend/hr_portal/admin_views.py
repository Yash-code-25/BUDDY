"""Home tiles, filter options, settings and the audit log."""
from datetime import date

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response as ApiResponse

from compass_app.models import AuditLog, Buddy, Joiner, Pairing, Settings

from . import audit
from .access import AdminView
from .people import values_in_use
from .pool import count_without_profile


class HomeView(AdminView):
    def get(self, request):
        today = timezone.localdate()
        joiners = Joiner.objects.all()
        buddies = Buddy.objects.all()
        J, P = Joiner.Status, Buddy.PoolStatus

        def n(status):
            return joiners.filter(compass_status=status).count()

        waiting = list(joiners.filter(compass_status=J.AWAITING_PAIRING))
        urgent = sum(1 for j in waiting if (j.date_of_joining - today).days <= 3)
        not_done = count_without_profile()
        active_pairings = Pairing.objects.filter(status=Pairing.Status.ACTIVE).count()

        tiles = [
            {"key": "awaiting_assessment", "label": "Joiners awaiting assessment",
             "count": n(J.AWAITING_ASSESSMENT), "link": "/hr/joiners?status=AWAITING_ASSESSMENT"},
            {"key": "awaiting_pairing", "label": "Joiners awaiting pairing",
             "count": len(waiting), "urgent": urgent, "link": "/hr/joiners?status=AWAITING_PAIRING"},
            {"key": "manual", "label": "Joiners routed to manual pairing",
             "count": n(J.MANUAL), "link": "/hr/joiners?status=MANUAL"},
            {"key": "active_pairings", "label": "Joiners in their induction",
             "count": active_pairings, "link": "/hr/joiners?status=PAIRED"},
            {"key": "pool", "label": "Buddies in pool (Active)",
             "count": buddies.filter(pool_status=P.ACTIVE).count(),
             "detail": f"{buddies.filter(pool_status=P.PAUSED).count()} paused",
             "link": "/hr/buddies?status=ACTIVE"},
            {"key": "buddies_pending", "label": "Buddies yet to complete their profile",
             "count": not_done, "link": "/hr/buddies?cmpbd=not_started,in_progress"},
        ]
        return ApiResponse({"tiles": tiles})


class FilterOptionsView(AdminView):
    """Values for the drop-downs: departments and locations from the lists in Settings, brands from
    the people already in COMPASS."""

    def get(self, request):
        s = Settings.load()
        return ApiResponse({
            "department": s.departments,
            "location": s.locations,
            "brand": sorted(b for b in values_in_use("brand") if b),
        })


# ---------- settings ----------

INT_FIELDS = {
    "close_gap": (0, 3), "strong_threshold": (1, 5), "good_threshold": (1, 5),
    "weaker_threshold": (1, 5), "amber_gap": (1, 4), "red_gap": (1, 4),
    "candidates_per_tier": (1, 10), "manual_cutoff_day": (0, 30), "old_answers_months": (1, 60),
}
TEXT_FIELDS = ["joiner_intro", "buddy_intro"]
# What the pre-joining emails show. These may be blank: the email then leaves that line out.
EMAIL_FIELDS = [
    "story_video_link", "handbook_link", "linkedin_link", "instagram_link",
    "dress_code", "contact_phone",
]
LIST_FIELDS = {"departments": ("department", "Departments"), "locations": ("location", "Locations")}
ALL_FIELDS = [*INT_FIELDS, *TEXT_FIELDS, *EMAIL_FIELDS, *LIST_FIELDS, "office_details"]
OFFICE_LIMITS = {"address": 300, "map_link": 500}


def clean_offices(value, locations) -> dict:
    """{location: {address, map_link}} for locations on the list, blanks dropped."""
    if not isinstance(value, dict):
        raise ValidationError("Office details must be one entry per location.")
    offices = {}
    for location, office in value.items():
        if location not in locations or not isinstance(office, dict):
            continue  # a location no longer on the list
        entry = {}
        for field, limit in OFFICE_LIMITS.items():
            text = str(office.get(field, "") or "").strip()
            if len(text) > limit:
                raise ValidationError(f"{location}: {field.replace('_', ' ')} can be at most {limit} characters.")
            if text:
                entry[field] = text
        if entry:
            offices[location] = entry
    return offices


def clean_list(value, field, label) -> list:
    """One entry each, as typed, in the admin's order. An entry still used by a joiner or buddy
    cannot go: they would be left with a value no form offers."""
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be a list.")
    entries = []
    for item in value:
        item = str(item).strip()
        if item and item.lower() not in (e.lower() for e in entries):
            entries.append(item)
    if not entries:
        raise ValidationError(f"{label} needs at least one entry.")
    kept = {e.lower() for e in entries}
    still_used = sorted(v for v in values_in_use(field) if v.lower() not in kept)
    if still_used:
        raise ValidationError(
            f"{label}: {', '.join(still_used)} cannot be removed while joiners or buddies have it. "
            "Change them first.")
    return entries


def settings_payload(s: Settings) -> dict:
    return {f: getattr(s, f) for f in ALL_FIELDS}


class SettingsView(AdminView):
    def get(self, request):
        return ApiResponse(settings_payload(Settings.load()))

    def put(self, request):
        s = Settings.load()
        before = settings_payload(s)
        new = {}
        for field, (low, high) in INT_FIELDS.items():
            value = request.data.get(field, before[field])
            if isinstance(value, str) and value.strip().isdigit():
                value = int(value)
            if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
                raise ValidationError(f"{field.replace('_', ' ')} must be a whole number from {low} to {high}.")
            new[field] = value

        for field in TEXT_FIELDS:
            text = str(request.data.get(field, before[field])).strip()
            if not text:
                raise ValidationError(f"{field.replace('_', ' ')} cannot be empty.")
            new[field] = text

        for field in EMAIL_FIELDS:
            text = str(request.data.get(field, before[field]) or "").strip()
            limit = Settings._meta.get_field(field).max_length
            if limit and len(text) > limit:
                raise ValidationError(f"{field.replace('_', ' ').capitalize()} can be at most {limit} characters.")
            new[field] = text

        for field, (person_field, label) in LIST_FIELDS.items():
            new[field] = clean_list(request.data.get(field, before[field]), person_field, label)
        new["office_details"] = clean_offices(request.data.get("office_details", before["office_details"]),
                                              new["locations"])

        if not new["strong_threshold"] >= new["good_threshold"] >= new["weaker_threshold"]:
            raise ValidationError("Strong, Good and Weaker thresholds must be in that order, high to low.")
        if new["amber_gap"] >= new["red_gap"]:
            raise ValidationError("The Amber gap must be smaller than the Red gap.")

        for field, value in new.items():
            setattr(s, field, value)
        s.save()
        changed = {k: v for k, v in new.items() if before[k] != v}
        if changed:
            AuditLog.record("settings_changed", s, user=request.user,
                            before={k: before[k] for k in changed}, after=changed)
        return ApiResponse(settings_payload(s))


# ---------- audit log ----------

class AuditLogView(AdminView):
    def get(self, request):
        q = request.query_params
        logs = AuditLog.objects.select_related("user")
        if q.get("user"):
            logs = logs.filter(user__username__icontains=q["user"])
        if q.get("action"):
            logs = logs.filter(action__icontains=q["action"])
        for key, lookup in (("date_from", "created_at__date__gte"), ("date_to", "created_at__date__lte")):
            if q.get(key):
                try:
                    logs = logs.filter(**{lookup: date.fromisoformat(q[key])})
                except ValueError:
                    raise ValidationError("Dates must look like 2026-11-02.")
        # Each entry as a plain sentence with names, and what changed in words (hr_portal/audit.py).
        return ApiResponse(audit.describe(list(logs[:500])))

