"""Day-based rules. run_all() is safe to run as often as you like: each email is sent once."""
from datetime import date, timedelta

from django.utils import timezone

from compass_app.models import AuditLog, Buddy, Joiner, QuestionSet, Response, Settings

from . import emails
from .models import Notification

BUDDY_FIRST_REMINDER_AFTER_DAYS = 5
BUDDY_REMINDER_EVERY_DAYS = 7
BUDDY_MAX_REMINDERS = 3


def _days_to_joining(joiner: Joiner, today: date) -> int:
    return (joiner.date_of_joining - today).days


def route_overdue_to_manual(today: date) -> int:
    """Joiners with no answers after their due day go to manual pairing, and the admins are told.
    Due: `manual_cutoff_day` days before joining, or 2 days after being added for short notice."""
    cutoff = Settings.load().manual_cutoff_day
    count = 0
    for joiner in Joiner.objects.filter(compass_status=Joiner.Status.AWAITING_ASSESSMENT):
        days = _days_to_joining(joiner, today)
        if today <= joiner.quiz_due(cutoff):
            continue
        joiner.compass_status = Joiner.Status.MANUAL
        joiner.save(update_fields=["compass_status"])
        AuditLog.record("routed_to_manual", joiner, after={"reason": "no assessment by cut-off", "days_to_joining": days})
        emails.alert_admins(
            f"manual_cutoff:{joiner.pk}",
            f"{joiner.name} has not taken the assessment",
            f"{joiner.name} joins on {joiner.date_of_joining:%d %b %Y} and has not submitted "
            "their COMPASS answers. They are routed to manual pairing.\n\n"
            f"Open: {emails.frontend_url()}/hr/joiners/{joiner.pk}",
            joiner=joiner,
        )
        count += 1
    return count


def send_buddy_reminders(today: date) -> int:
    """Remind buddies who have not completed their profile, weekly, at most 3 times."""
    done = set(
        Response.objects.filter(
            assessment_code=Response.Code.BUDDY, question_set=QuestionSet.active(), submitted_at__isnull=False
        ).values_list("buddy_id", flat=True)
    )
    count = 0
    for buddy in Buddy.objects.exclude(pool_status=Buddy.PoolStatus.REMOVED):
        if buddy.pk in done:
            continue
        # Send the next reminder that is due: one per run, up to BUDDY_MAX_REMINDERS in total.
        for number in range(1, BUDDY_MAX_REMINDERS + 1):
            if Notification.objects.filter(key=f"buddy_reminder:{buddy.pk}:{number}").exists():
                continue
            due_on = buddy.date_added_to_pool + timedelta(
                days=BUDDY_FIRST_REMINDER_AFTER_DAYS + BUDDY_REMINDER_EVERY_DAYS * (number - 1)
            )
            if today >= due_on and emails.send_buddy_reminder(buddy, number):
                count += 1
            break
    return count


def run_all(today: date | None = None) -> dict:
    from feedback.jobs import close_finished_pairings, send_review_requests

    from .prejoining import send_all_due

    today = today or timezone.localdate()
    return {
        "review_requests": send_review_requests(today),
        "closed_pairings": close_finished_pairings(today),
        "prejoining_emails": send_all_due(today),
        "routed_to_manual": route_overdue_to_manual(today),
        "buddy_reminders": send_buddy_reminders(today),
    }
