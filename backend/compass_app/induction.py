"""The 4-week induction programme as one joiner sees it: every item, and which they have ticked."""
from django.utils import timezone

from .models import InductionItem, Pairing

WEEKS = (1, 2, 3, 4)


def current_pairing(joiner):
    """The joiner's buddy pairing (active or finished), or None. A changed one does not count."""
    return (
        Pairing.objects.filter(joiner=joiner).exclude(status=Pairing.Status.CANCELLED)
        .select_related("buddy").order_by("-assigned_at").first()
    )


def progress(joiner, start_date=None) -> dict:
    items = list(InductionItem.objects.all())
    done = set(joiner.induction_ticks.values_list("item_id", flat=True))
    week = None
    if start_date:
        days_in = (timezone.localdate() - start_date).days
        week = None if days_in < 0 else min(4, days_in // 7 + 1)
    return {
        "start_date": start_date,
        "current_week": week,  # None before day 1
        "done": sum(1 for i in items if i.pk in done),
        "total": len(items),
        "weeks": [
            {
                "week": w,
                "items": [
                    {"id": i.pk, "day": i.day, "activity": i.activity, "owner": i.owner, "done": i.pk in done}
                    for i in items if i.week == w
                ],
            }
            for w in WEEKS
        ],
    }
