"""API answers change from one minute to the next (a renewed quiz link, a new pairing), so the browser
must never reuse one. Without this it may keep showing a 410 "link expired" or a 404 from its cache."""
from django.utils.cache import add_never_cache_headers


def never_cache_api(get_response):
    def middleware(request):
        response = get_response(request)
        if request.path.startswith("/api/"):
            add_never_cache_headers(response)
        return response

    return middleware
