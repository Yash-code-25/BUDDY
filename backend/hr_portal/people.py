"""Validation and CSV import for joiners and buddies. The CSV import stands in for the HRMS feed."""
import csv
import io
import logging
from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from compass_app.models import AuditLog, Buddy, Joiner, Pairing, Settings
from employee_portal.credentials import issue_login
from notifications import prejoining

logger = logging.getLogger(__name__)

COMMON = ["name", "department", "location", "brand", "function", "designation", "designation_track"]
# A joiner's Day 1 details for the pre-joining emails. All optional; a blank one leaves its line out.
DAY_ONE = ["manager_name", "reporting_time", "contact_person", "directions"]


class RowError(Exception):
    pass


def _require(row, keys):
    missing = [k for k in keys if not str(row.get(k, "")).strip()]
    if missing:
        raise RowError("Missing: " + ", ".join(missing))


def _email(value, label):
    try:
        validate_email(value)
    except DjangoValidationError:
        raise RowError(f"{label} is not a valid email address")


def _from_list(value, allowed, label):
    """The list's own spelling of `value`, so "sales" is stored as "Sales". The match compares these
    exactly, so a value outside the list would never meet anyone."""
    spelt = next((a for a in allowed if a.lower() == value.lower()), None)
    if spelt is None:
        raise RowError(f"{label} must be one of: {', '.join(allowed)} (the list is in Settings)")
    return spelt


def _common(row) -> dict:
    data = {k: str(row.get(k, "")).strip() for k in COMMON}
    s = Settings.load()
    data["department"] = _from_list(data["department"], s.departments, "Department")
    data["location"] = _from_list(data["location"], s.locations, "Location")
    track = data["designation_track"].upper()
    if track and (len(track) != 1 or track not in "ABCDE"):
        raise RowError("designation_track must be A, B, C, D or E")
    data["designation_track"] = track
    return data


def clean_joiner(row) -> tuple:
    _require(row, ["candidate_id", "name", "personal_email", "department", "location", "date_of_joining"])
    _email(row["personal_email"], "personal_email")
    try:
        doj = date.fromisoformat(str(row["date_of_joining"]).strip())
    except ValueError:
        raise RowError("date_of_joining must look like 2026-12-01")
    data = _common(row)
    data["personal_email"] = row["personal_email"].strip()
    data["reporting_manager_id"] = str(row.get("reporting_manager_id", "")).strip()
    data["date_of_joining"] = doj
    # Only the Day 1 columns the CSV or form has, so an import without them keeps what is there.
    data.update({k: str(row[k]).strip() for k in DAY_ONE if k in row})
    return str(row["candidate_id"]).strip(), data


def clean_buddy(row) -> tuple:
    _require(row, ["employee_id", "name", "email", "department", "location"])
    _email(row["email"], "email")
    data = _common(row)
    data["email"] = row["email"].strip()
    data["manager_id"] = str(row.get("manager_id", "")).strip()
    if str(row.get("intro", "")).strip():
        data["intro"] = str(row["intro"]).strip()
    historic = str(row.get("total_joiners_buddied", "")).strip()
    if historic:
        if not historic.isdigit():
            raise RowError("total_joiners_buddied must be a whole number")
        data["total_joiners_buddied"] = int(historic)
    return str(row["employee_id"]).strip(), data


def welcome(person, kind, today=None):
    """Email someone just added. A buddy gets their login details. A joiner gets 1 Welcome, then
    2 their login details (with the questions to answer), then any later email whose day has
    already passed (see notifications/prejoining.py)."""
    if kind != "joiner":
        issue_login(person, kind)
        return
    person.added_on = today or timezone.localdate()
    person.save(update_fields=["added_on"])
    try:
        prejoining.welcome(person, Settings.load(), person.added_on)
    except Exception:
        logger.exception("Could not send the welcome email to joiner %s", person.pk)
    issue_login(person, kind)
    try:
        prejoining.send_due(person, person.added_on)
    except Exception:
        logger.exception("Could not send the pre-joining emails to joiner %s", person.pk)


def read_rows(text: str) -> list:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in reader]


def check_joining_date(existing, data):
    """A joiner with a buddy keeps their joining date: the pairing's Day 1 to Day 30 and the
    induction weeks are counted from it, and they are never edited."""
    if existing is None or data["date_of_joining"] == existing.date_of_joining:
        return
    if existing.pairings.filter(status=Pairing.Status.ACTIVE).exists():
        raise RowError("The joining date cannot change once the joiner has a buddy pairing.")


# What differs between joiners and buddies: (model, id field, clean, kind, created-by field)
JOINERS = (Joiner, "candidate_id", clean_joiner, "joiner", None)
BUDDIES = (Buddy, "employee_id", clean_buddy, "buddy", "added_by")


def _import(text: str, user, people, check=None) -> dict:
    """Add or update one person per CSV row. New people are emailed their login details."""
    model, key_field, clean, kind, created_by = people
    created = updated = 0
    errors = []
    for number, row in enumerate(read_rows(text), start=2):
        try:
            key, data = clean(row)
            if check:
                check(model.objects.filter(**{key_field: key}).first(), data)
        except RowError as e:
            errors.append({"row": number, "error": str(e)})
            continue
        extra = {created_by: user} if created_by else {}
        person, was_created = model.objects.update_or_create(
            **{key_field: key}, defaults=data, create_defaults={**data, **extra},
        )
        if was_created:
            welcome(person, kind)
        created += was_created
        updated += not was_created
    AuditLog.record(f"{model._meta.verbose_name_plural.lower()}_imported", user=user, object_type=model.__name__,
                    after={"created": created, "updated": updated, "errors": len(errors)})
    return {"created": created, "updated": updated, "errors": errors}


def import_joiners(text: str, user) -> dict:
    return _import(text, user, JOINERS, check=check_joining_date)


def import_buddies(text: str, user) -> dict:
    return _import(text, user, BUDDIES)


def create_person(row, user, people, action):
    """Add one joiner or buddy from the admin's form and email them their login details."""
    model, key_field, clean, kind, created_by = people
    try:
        key, data = clean({**row})
    except RowError as e:
        raise ValidationError(str(e))
    if model.objects.filter(**{key_field: key}).exists():
        raise ValidationError(f"A {kind} with that {key_field.replace('_', ' ')} already exists.")
    person = model.objects.create(**{key_field: key}, **data, **({created_by: user} if created_by else {}))
    AuditLog.record(action, person, user=user, after={"name": person.name})
    welcome(person, kind)
    return person


def values_in_use(field) -> set:
    """Every value of `field` that a joiner or buddy has."""
    return set(Joiner.objects.values_list(field, flat=True)) | set(Buddy.objects.values_list(field, flat=True))
