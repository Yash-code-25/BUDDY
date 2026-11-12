"""Reports: four numbers at a glance and two plain tables (buddies and buddy reviews). Joiners have
their own page.
Each table can be downloaded as Excel or CSV. Rows about a buddy carry the buddy's id so the name
can open the buddy panel."""
import csv
import io
from collections import defaultdict
from datetime import date, datetime

from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework.response import Response as ApiResponse

from compass_app.models import Buddy, Joiner, Pairing
from feedback.models import Feedback

from .access import AdminView
from .pool import cmpbd_status, profile_responses


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%Y-%m-%d") if timezone.is_aware(value) else value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    return value


def buddies_table():
    responses = profile_responses()
    reviews = defaultdict(list)
    for f in Feedback.objects.select_related("pairing"):
        reviews[f.pairing.buddy_id].append(f.average())

    rows, buddy_ids, attention = [], [], []
    for b in Buddy.objects.order_by("name"):
        done = cmpbd_status(responses.get(b.pk)) == "completed"
        scores = reviews.get(b.pk)
        rows.append([
            b.name, b.department, b.location, b.get_pool_status_display(), "Done" if done else "Not yet",
            b.active_joiners, b.total_joiners_buddied, round(sum(scores) / len(scores), 1) if scores else "",
        ])
        buddy_ids.append(b.pk)
        attention.append(not done and b.pool_status != Buddy.PoolStatus.REMOVED)
    columns = ["Buddy", "Department", "Location", "Pool status", "Profile", "Joiners now",
               "Joiners in total", "Average review (of 5)"]
    return columns, rows, buddy_ids, attention


def reviews_table():
    rows, buddy_ids = [], []
    for f in Feedback.objects.select_related("pairing__joiner", "pairing__buddy").order_by("-submitted_at"):
        p = f.pairing
        rows.append([p.joiner.name, p.buddy.name, f.submitted_at, f.q1, f.q2, f.q3, f.average(), f.comment])
        buddy_ids.append(p.buddy_id)
    columns = ["Joiner", "Buddy", "Date", "Helpful", "Easy to reach", "Would recommend", "Average", "Comment"]
    return columns, rows, buddy_ids, [False] * len(rows)


TABLES = {"buddies": ("Buddies", buddies_table),
          "reviews": ("Buddy reviews", reviews_table)}


class ReportSummaryView(AdminView):
    """The four numbers at the top of the Reports page: buddies, joiners, joiners given a buddy,
    and the average buddy review."""

    def get(self, request):
        buddies = Buddy.objects.exclude(pool_status=Buddy.PoolStatus.REMOVED)
        # A joiner whose buddy was changed has a cancelled pairing too: count each joiner once.
        assigned = (Pairing.objects.exclude(status=Pairing.Status.CANCELLED)
                    .values("joiner_id").distinct().count())
        averages = [f.average() for f in Feedback.objects.all()]
        return ApiResponse({
            "total_buddies": buddies.count(),
            "active_buddies": buddies.filter(pool_status=Buddy.PoolStatus.ACTIVE).count(),
            "total_joiners": Joiner.objects.count(),
            "total_assigned": assigned,
            "in_induction": Pairing.objects.filter(status=Pairing.Status.ACTIVE).count(),
            "average_review": round(sum(averages) / len(averages), 1) if averages else None,
            "reviews": len(averages),
        })


def xlsx_response(title, columns, rows, filename):
    """One sheet: a header row, then the rows, as an Excel download."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]  # Excel's limit for a sheet name
    ws.append(columns)
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    response = HttpResponse(
        out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ReportView(AdminView):
    def get(self, request, name):
        if name not in TABLES:
            raise Http404
        title, build = TABLES[name]
        columns, raw_rows, buddy_ids, attention = build()
        rows = [[fmt(v) for v in row] for row in raw_rows]

        export = request.query_params.get("export", "")
        if export == "csv":
            out = io.StringIO()
            writer = csv.writer(out)
            writer.writerow(columns)
            writer.writerows(rows)
            response = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="compass-{name}.csv"'
            return response
        if export == "xlsx":
            return xlsx_response(title, columns, rows, f"compass-{name}.xlsx")

        return ApiResponse({
            "name": name, "title": title, "columns": columns, "rows": rows,
            "buddy_column": next((i for i, c in enumerate(columns) if c == "Buddy"), None),
            "buddy_ids": buddy_ids,
            "attention": attention,  # rows that need someone to act: no buddy yet, or no profile yet
        })
