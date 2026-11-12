"""After the 4-week induction: ask the joiner to review their buddy, and close the pairing at Day 30."""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import F

from compass_app.models import AuditLog, Buddy, Joiner, Pairing
from notifications import emails

LATE_WINDOW_DAYS = 14  # stop emailing about a review this many days after it opened


def send_review_requests(today: date) -> int:
    count = 0
    pairings = Pairing.objects.exclude(status=Pairing.Status.CANCELLED).filter(
        review__isnull=True,
        start_date__lte=today - timedelta(days=Pairing.REVIEW_AFTER_DAYS),
        start_date__gte=today - timedelta(days=Pairing.REVIEW_AFTER_DAYS + LATE_WINDOW_DAYS),
    ).select_related("joiner", "buddy")
    for pairing in pairings:
        if emails.send_review_request(pairing):
            count += 1
    return count


def close_finished_pairings(today: date) -> int:
    """After Day 30 the pairing closes: the buddy's active count drops and the joiner is closed."""
    count = 0
    for pairing in Pairing.objects.filter(status=Pairing.Status.ACTIVE, end_date__lt=today):
        with transaction.atomic():
            pairing.status = Pairing.Status.CLOSED
            pairing.save(update_fields=["status"])
            Buddy.objects.filter(pk=pairing.buddy_id, active_joiners__gt=0).update(
                active_joiners=F("active_joiners") - 1
            )
            Joiner.objects.filter(pk=pairing.joiner_id).update(compass_status=Joiner.Status.CLOSED)
            AuditLog.record("pairing_closed", pairing, after={"end_date": str(pairing.end_date)})
        count += 1
    return count
