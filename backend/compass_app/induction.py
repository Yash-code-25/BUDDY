"""The 4-week induction plan as one joiner sees it: the common Day 1 every joiner gets, then their
own plan from Day 2 to the end of week 4, and which items they have ticked."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import InductionItem, InductionTick, Pairing

WEEKS = (1, 2, 3, 4)


def current_pairing(joiner):
    """The joiner's buddy pairing (active or finished), or None. A changed one does not count."""
    return (
        Pairing.objects.filter(joiner=joiner).exclude(status=Pairing.Status.CANCELLED)
        .select_related("buddy").order_by("-assigned_at").first()
    )


def is_day_one(item) -> bool:
    """A common Day 1 row, or a joiner's own copy of one."""
    return item.joiner_id is None or item.day_one


def items_for(joiner):
    """Day 1 first (the common rows, or the joiner's own copy of them), then the joiner's own rows,
    each week in order."""
    if joiner.own_day_one:
        items = InductionItem.objects.filter(joiner=joiner)
    else:
        items = InductionItem.objects.filter(Q(joiner__isnull=True) | Q(joiner=joiner))
    return sorted(items, key=lambda i: (i.week, not is_day_one(i), i.position, i.pk))


def belongs_to(item, joiner) -> bool:
    if item.joiner_id is None:
        return not joiner.own_day_one
    return item.joiner_id == joiner.pk


@transaction.atomic
def make_own_day_one(joiner) -> dict:
    """Give the joiner their own copy of the common Day 1, so it can be changed for them alone.
    Their ticks move to the copies. Returns {common row id: their copy}. Does nothing the second time."""
    joiner = type(joiner).objects.select_for_update().get(pk=joiner.pk)
    if joiner.own_day_one:
        return {i.copied_from_id: i for i in InductionItem.objects.filter(joiner=joiner, day_one=True)
                if i.copied_from_id}
    copies = {}
    for common in InductionItem.objects.filter(joiner__isnull=True):
        copies[common.pk] = InductionItem.objects.create(
            joiner=joiner, week=1, day=common.day, activity=common.activity, owner=common.owner,
            position=common.position, day_one=True, copied_from=common,
        )
    for tick in InductionTick.objects.filter(joiner=joiner, item_id__in=copies):
        tick.item = copies[tick.item_id]
        tick.save(update_fields=["item"])
    joiner.own_day_one = True
    joiner.save(update_fields=["own_day_one"])
    return copies


@transaction.atomic
def use_common_day_one(joiner):
    """Undo make_own_day_one: drop the joiner's Day 1 copies and give them the common rows again.
    A ticked copy of a common row that still exists stays ticked."""
    for copy in InductionItem.objects.filter(joiner=joiner, day_one=True):
        if copy.copied_from_id and copy.ticks.filter(joiner=joiner).exists():
            InductionTick.objects.get_or_create(joiner=joiner, item_id=copy.copied_from_id)
        copy.delete()
    type(joiner).objects.filter(pk=joiner.pk).update(own_day_one=False)
    joiner.own_day_one = False


def percent(done: int, total: int) -> int:
    return round(done * 100 / total) if total else 0


def progress(joiner, start_date=None) -> dict:
    items = items_for(joiner)
    done = set(joiner.induction_ticks.values_list("item_id", flat=True))
    week = None
    if start_date:
        days_in = (timezone.localdate() - start_date).days
        week = None if days_in < 0 else min(4, days_in // 7 + 1)
    finished = sum(1 for i in items if i.pk in done)
    return {
        "start_date": start_date,
        "current_week": week,  # None before day 1
        "done": finished,
        "total": len(items),
        "percent": percent(finished, len(items)),
        "own_day_one": joiner.own_day_one,  # Day 1 was changed for this joiner alone
        "weeks": [
            {
                "week": w,
                "items": [
                    {"id": i.pk, "day": i.day, "activity": i.activity, "owner": i.owner,
                     "done": i.pk in done, "common": i.joiner_id is None, "day_one": is_day_one(i)}
                    for i in items if i.week == w
                ],
            }
            for w in WEEKS
        ],
    }
