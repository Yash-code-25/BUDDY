"""Serve the built React app, so one Django server runs the whole application.

Run `npm run build` in the frontend folder (or `npm run watch` to rebuild as you edit). Django then
serves the files in frontend/dist and falls back to index.html for every page address, which is how a
single-page app handles /hr/joiners, /assess/... and the rest."""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_safe
from django.views.static import serve

# These belong to Django. An unknown address under them is a real 404, never the React page.
DJANGO_PREFIXES = ("api/", "admin/", "static/")


@require_safe
def frontend(request, path=""):
    if path.startswith(DJANGO_PREFIXES):
        raise Http404

    dist = Path(settings.FRONTEND_DIST).resolve()
    index = dist / "index.html"
    if not index.is_file():
        return HttpResponse(
            "The web app has not been built yet.\n\n"
            "In a terminal, run:  cd frontend  then  npm run build\n"
            "and reload this page.",
            status=503, content_type="text/plain; charset=utf-8",
        )

    if path:
        candidate = (dist / path).resolve()
        # a real file inside dist (a script, a stylesheet, the icon), never anything outside it
        if candidate.is_file() and dist in candidate.parents:
            return serve(request, candidate.relative_to(dist).as_posix(), document_root=dist)

    response = FileResponse(open(index, "rb"), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"  # a rebuild changes the script names inside index.html
    return response
