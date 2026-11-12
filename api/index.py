"""Vercel's entry point: hands every /api, /admin and /static request to COMPASS's Django app.

The React screens (frontend/dist) are served by Vercel directly; vercel.json sends only Django's
addresses here. The Django code itself lives in backend/.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402  (needs the path above)

app = application  # Vercel looks for a WSGI app named "app"
