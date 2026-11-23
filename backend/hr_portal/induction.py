"""The induction plans. Day 1 is common: every joiner gets the same rows. From Day 2 to the end of
week 4 each joiner has their own plan, which the Program admin writes on that joiner's page."""
from collections import defaultdict

from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response as ApiResponse

from compass_app.induction import current_pairing, make_own_day_one, percent, progress, use_common_day_one
from compass_app.models import AuditLog, InductionItem, InductionTick, Joiner, Pairing

from .access import AdminView


def item_payload(item):
    return {"id": item.pk, "week": item.week, "day": item.day, "activity": item.activity, "owner": item.owner}


def clean(data, current=None, common=False) -> dict:
    current = current or {}
    if common:  # the common rows are all Day 1
        week = 1
    else:
        week = data.get("week", current.get("week"))
        if isinstance(week, str) and week.strip().isdigit():
            week = int(week)
        if not isinstance(week, int) or isinstance(week, bool) or not 1 <= week <= 4:
            raise ValidationError("Week must be 1, 2, 3 or 4.")
    out = {"week": week}
    for field, label, size, required in (("day", "Day", 40, True), ("activity", "Activity", 200, True),
                                         ("owner", "With", 100, False)):
        value = str(data.get(field, current.get(field, ""))).strip()
        if required and not value:
            raise ValidationError(f"{label} cannot be empty.")
        out[field] = value[:size]
    return out


def add_item(request, joiner=None):
    data = clean(request.data, common=joiner is None)
    # "Day 1" in week 1 of a joiner's plan joins their Day 1, which becomes their own to change.
    day_one = joiner is not None and data["week"] == 1 and data["day"].lower() == "day 1"
    if day_one:
        make_own_day_one(joiner)
    last = InductionItem.objects.filter(joiner=joiner, week=data["week"], day_one=day_one).aggregate(
        n=Max("position"))["n"]
    item = InductionItem.objects.create(**data, joiner=joiner, position=(last or 0) + 1, day_one=day_one)
    AuditLog.record("induction_item_added", item, user=request.user,
                    after={**data, **({"joiner": joiner.name} if joiner else {})})
    return ApiResponse(item_payload(item), status=201)


def joiner_info(joiner, buddy=None):
    return {
        "id": joiner.pk, "name": joiner.name, "candidate_id": joiner.candidate_id,
        "department": joiner.department, "location": joiner.location,
        "date_of_joining": joiner.date_of_joining, "status": joiner.compass_status,
        "buddy": buddy.name if buddy else None,
    }


class InductionListView(AdminView):
    """The common Day 1 rows, which every joiner gets."""

    def get(self, request):
        return ApiResponse([item_payload(i) for i in InductionItem.objects.filter(joiner__isnull=True)])

    def post(self, request):
        return add_item(request)


def target_item(request, pk):
    """The row to change. On a joiner's page (?joiner=<id>) a common Day 1 row is not changed for
    everyone: the joiner gets their own copy of Day 1 and the change goes to their copy."""
    item = get_object_or_404(InductionItem, pk=pk)
    joiner_id = request.query_params.get("joiner", "")
    if item.joiner_id is None and joiner_id.isdigit():
        joiner = get_object_or_404(Joiner, pk=int(joiner_id))
        item = make_own_day_one(joiner).get(item.pk)
        if item is None:  # a common row added after their Day 1 became their own: not in their plan
            raise NotFound("That row is not in this joiner's plan.")
    return item


class InductionItemView(AdminView):
    """Edit or remove one row, common or a joiner's own."""

    def patch(self, request, pk):
        item = target_item(request, pk)
        before = item_payload(item)
        # A Day 1 row (common, or a joiner's copy) stays in week 1.
        data = clean(request.data, before, common=item.joiner_id is None or item.day_one)
        if data["week"] != item.week:  # moved to another week: put it last there
            last = InductionItem.objects.filter(joiner=item.joiner_id, week=data["week"]).aggregate(n=Max("position"))["n"]
            item.position = (last or 0) + 1
        for field, value in data.items():
            setattr(item, field, value)
        item.save()
        AuditLog.record("induction_item_edited", item, user=request.user,
                        before={k: before[k] for k in data}, after=data)
        return ApiResponse(item_payload(item))

    def delete(self, request, pk):
        item = target_item(request, pk)
        AuditLog.record("induction_item_removed", item, user=request.user, before=item_payload(item))
        item.delete()
        return ApiResponse(status=204)


class InductionJoinersView(AdminView):
    """Every joiner with how much of their induction they have ticked. The Induction page and the
    Joiner review report both list it."""

    def get(self, request):
        common = set(InductionItem.objects.filter(joiner__isnull=True).values_list("pk", flat=True))
        own = defaultdict(set)
        for item_id, joiner_id in InductionItem.objects.filter(joiner__isnull=False).values_list("pk", "joiner_id"):
            own[joiner_id].add(item_id)
        ticks = defaultdict(set)
        for joiner_id, item_id in InductionTick.objects.values_list("joiner_id", "item_id"):
            ticks[joiner_id].add(item_id)
        buddies = {}
        pairings = (Pairing.objects.exclude(status=Pairing.Status.CANCELLED)
                    .select_related("buddy").order_by("assigned_at"))
        for p in pairings:  # the latest one wins
            buddies[p.joiner_id] = p.buddy

        rows = []
        for joiner in Joiner.objects.order_by("-date_of_joining", "name"):
            plan = own[joiner.pk] if joiner.own_day_one else common | own[joiner.pk]
            done = len(ticks[joiner.pk] & plan)
            rows.append({
                **joiner_info(joiner, buddies.get(joiner.pk)),
                "own_items": len(own[joiner.pk]),
                "done": done, "total": len(plan), "percent": percent(done, len(plan)),
            })
        return ApiResponse(rows)


class InductionJoinerView(AdminView):
    """GET: one joiner's whole plan, common Day 1 included, with their ticks.
    POST {week, day, activity, owner}: add a row to their own plan."""

    def get(self, request, pk):
        joiner = get_object_or_404(Joiner, pk=pk)
        pairing = current_pairing(joiner)
        return ApiResponse({
            "joiner": joiner_info(joiner, pairing.buddy if pairing else None),
            "induction": progress(joiner, pairing.start_date if pairing else joiner.date_of_joining),
        })

    def post(self, request, pk):
        return add_item(request, get_object_or_404(Joiner, pk=pk))


class InductionJoinerDayOneView(AdminView):
    """DELETE: the joiner goes back to the common Day 1, dropping the changes made for them alone."""

    def delete(self, request, pk):
        joiner = get_object_or_404(Joiner, pk=pk)
        if joiner.own_day_one:
            use_common_day_one(joiner)
            AuditLog.record("induction_day_one_reset", joiner, user=request.user)
        return ApiResponse(status=204)
