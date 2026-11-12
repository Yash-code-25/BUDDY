"""The Clubs page: joiners and buddies grouped by what they enjoy, at each location."""
from compass_app.clubs import INTERESTS, all_clubs
from compass_app.models import Settings
from rest_framework.response import Response as ApiResponse

from .access import AdminView


class ClubsView(AdminView):
    """GET ?location=&interest=: every club with its members."""

    def get(self, request):
        location = request.query_params.get("location", "")
        interest = request.query_params.get("interest", "")
        return ApiResponse({
            "clubs": all_clubs(location=location, interest=interest),
            "interests": INTERESTS,
            "locations": Settings.load().locations,
        })
