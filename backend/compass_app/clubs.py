"""Clubs: joiners and buddies who enjoy the same thing at the same location.

Everyone picks their interests in their portal from INTERESTS. A club is one interest at one location
(e.g. "Badminton · Pune") and its members are everyone there who picked it. Nothing is stored: clubs
are worked out from the people, so they fill and empty themselves. Removed buddies and closed
joiners are left out. Clubs never affect the buddy match.
"""
from .models import Buddy, Joiner

# What joiners and buddies can pick under "What you enjoy outside work".
INTERESTS = [
    "Cricket", "Football", "Badminton", "Running and fitness", "Yoga", "Books", "Cooking", "Music",
    "Movies", "Travel", "Photography", "Art and craft", "Gaming", "Volunteering",
]


def _people():
    joiners = Joiner.objects.exclude(compass_status=Joiner.Status.CLOSED).exclude(interests=[])
    buddies = Buddy.objects.exclude(pool_status=Buddy.PoolStatus.REMOVED).exclude(interests=[])
    return joiners, buddies


def all_clubs(location: str = "", interest: str = "") -> list:
    """Every club with at least one member, biggest first. Optionally one location or interest."""
    joiners, buddies = _people()
    clubs = {}

    def add(person, kind, row):
        if location and person.location != location:
            return
        for picked in person.interests:
            if picked not in INTERESTS or (interest and picked != interest):
                continue
            club = clubs.setdefault((picked, person.location), {
                "interest": picked, "location": person.location, "buddies": [], "joiners": [],
            })
            club[kind].append(row)

    for b in buddies.order_by("name"):
        add(b, "buddies", {"id": b.pk, "name": b.name, "department": b.department, "designation": b.designation})
    for j in joiners.order_by("date_of_joining", "name"):
        add(j, "joiners", {"id": j.pk, "name": j.name, "department": j.department,
                           "date_of_joining": j.date_of_joining, "status": j.get_compass_status_display()})
    return sorted(
        clubs.values(),
        key=lambda c: (-(len(c["buddies"]) + len(c["joiners"])), c["interest"], c["location"]),
    )


def joiners_in_clubs_of(buddy: Buddy) -> list:
    """For a buddy: their interests at their location, with the new joiners who share each one."""
    found = {c["interest"]: c for c in all_clubs(location=buddy.location)}
    return [
        {"interest": interest, "location": buddy.location,
         "joiners": [{"name": j["name"], "department": j["department"], "date_of_joining": j["date_of_joining"]}
                     for j in found[interest]["joiners"]]}
        for interest in buddy.interests if interest in found
    ]


def clubs_for(joiner: Joiner) -> list:
    """The joiner's clubs at their location, with the buddies in each (them excluded)."""
    found = {c["interest"]: c for c in all_clubs(location=joiner.location)}
    return [
        {"interest": interest, "location": joiner.location,
         "buddies": [{"name": b["name"], "department": b["department"]} for b in found[interest]["buddies"]]}
        for interest in joiner.interests if interest in found
    ]

