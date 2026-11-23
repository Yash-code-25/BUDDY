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
from feedback.questions import COUNT, SCALE
from feedback.questions import questions as review_questions

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


def asked(feedback, current) -> list:
    """The questions as this joiner saw them; reviews from before the wording was kept get today's."""
    return feedback.questions if len(feedback.questions or []) == COUNT else current


REVIEW_MAX = 5 * COUNT  # three questions, each out of 5


def reviews_table(export=False):
    """On screen: who, when and the total score; "View details" opens each answer and the comment.
    The download also has each score (the questions as worded in Settings now) and the comment."""
    current = review_questions()
    rows, buddy_ids = [], []
    for f in Feedback.objects.select_related("pairing__joiner", "pairing__buddy").order_by("-submitted_at"):
        p = f.pairing
        total = f"{sum(f.scores())} / {REVIEW_MAX}"
        if export:
            rows.append([p.joiner.name, p.buddy.name, f.submitted_at, *f.scores(), total, f.comment])
        else:
            rows.append([p.joiner.name, p.buddy.name, f.submitted_at, *f.scores(), total, ""])
        buddy_ids.append(p.buddy_id)
    # On screen the questions are Q1-Q3 (the full wording is too long for a column head).
    columns = (["Joiner", "Buddy", "Date", *current, "Total", "Comment"] if export
               else ["Joiner", "Buddy", "Date", *(f"Q{n}" for n in range(1, COUNT + 1)), "Total", "Details"])
    return columns, rows, buddy_ids, [False] * len(rows)


def review_details():
    """Each review in full, in the table's order: every question as the joiner saw it, with its score in words."""
    current = review_questions()
    return [
        {"questions": [{"question": q, "score": s, "label": SCALE[s - 1]}
                       for q, s in zip(asked(f, current), f.scores())],
         "total": sum(f.scores()), "max": REVIEW_MAX, "comment": f.comment}
        for f in Feedback.objects.order_by("-submitted_at")
    ]


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


def download(request, title, columns, rows, name):
    """The table as a file when the address asks for one (?export=csv or ?export=xlsx), else None."""
    export = request.query_params.get("export", "")
    rows = [[fmt(v) for v in row] for row in rows]
    if export == "csv":
        out = io.StringIO()
        out.write("﻿")  # so Excel reads names in other scripts correctly
        writer = csv.writer(out)
        writer.writerow(columns)
        writer.writerows(rows)
        response = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="compass-{name}.csv"'
        return response
    if export == "xlsx":
        return xlsx_response(title, columns, rows, f"compass-{name}.xlsx")
    return None


class ReportView(AdminView):
    def get(self, request, name):
        if name not in TABLES:
            raise Http404
        title, build = TABLES[name]
        exporting = request.query_params.get("export") in ("csv", "xlsx")
        columns, raw_rows, buddy_ids, attention = build(export=True) if name == "reviews" and exporting else build()
        rows = [[fmt(v) for v in row] for row in raw_rows]

        file = download(request, title, columns, rows, name)
        if file:
            return file

        return ApiResponse({
            "name": name, "title": title, "columns": columns, "rows": rows,
            "buddy_column": next((i for i, c in enumerate(columns) if c == "Buddy"), None),
            "buddy_ids": buddy_ids,
            "attention": attention,  # rows that need someone to act: no buddy yet, or no profile yet
            # a review row opens the joiner's answers in full
            **({"details": review_details()} if name == "reviews" else {}),
        })
