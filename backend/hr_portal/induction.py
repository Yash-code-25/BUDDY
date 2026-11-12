"""The Program admin writes the 4-week induction programme: a simple table of week, day, activity
and who it is with. Every joiner follows the same programme from their joining date."""
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response as ApiResponse

from compass_app.models import AuditLog, InductionItem

from .access import AdminView


def item_payload(item):
    return {"id": item.pk, "week": item.week, "day": item.day, "activity": item.activity, "owner": item.owner}


def clean(data, current=None) -> dict:
    current = current or {}
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


class InductionListView(AdminView):
    def get(self, request):
        return ApiResponse([item_payload(i) for i in InductionItem.objects.all()])

    def post(self, request):
        data = clean(request.data)
        last = InductionItem.objects.filter(week=data["week"]).aggregate(n=Max("position"))["n"]
        item = InductionItem.objects.create(**data, position=(last or 0) + 1)
        AuditLog.record("induction_item_added", item, user=request.user, after=data)
        return ApiResponse(item_payload(item), status=201)


class InductionItemView(AdminView):
    def patch(self, request, pk):
        item = get_object_or_404(InductionItem, pk=pk)
        before = item_payload(item)
        data = clean(request.data, before)
        if data["week"] != item.week:  # moved to another week: put it last there
            last = InductionItem.objects.filter(week=data["week"]).aggregate(n=Max("position"))["n"]
            item.position = (last or 0) + 1
        for field, value in data.items():
            setattr(item, field, value)
        item.save()
        AuditLog.record("induction_item_edited", item, user=request.user, before=before, after=data)
        return ApiResponse(item_payload(item))

    def delete(self, request, pk):
        item = get_object_or_404(InductionItem, pk=pk)
        AuditLog.record("induction_item_removed", item, user=request.user, before=item_payload(item))
        item.delete()
        return ApiResponse(status=204)
