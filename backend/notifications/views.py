"""The daily job as an address, for hosts that schedule by calling a URL (Vercel Cron).

Vercel calls GET /api/cron/daily/ once a day with "Authorization: Bearer <CRON_SECRET>". Anyone else
gets 403, and so does everyone while CRON_SECRET is not set. It does the same as
`python manage.py run_daily`, which a normal server can keep using instead.
"""
import hmac

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .jobs import run_all


@require_GET
def daily(request):
    secret = settings.CRON_SECRET
    given = request.headers.get("Authorization", "")
    if not secret or not hmac.compare_digest(given, f"Bearer {secret}"):
        return JsonResponse({"error": "Not allowed."}, status=403)
    return JsonResponse({"ok": True, "done": run_all()})
