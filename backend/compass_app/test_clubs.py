"""Clubs: joiners and buddies who picked the same interest at the same location."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from .clubs import all_clubs, clubs_for
from .models import Buddy, Joiner

SOON = date.today() + timedelta(days=20)


def buddy(eid, name, location="Pune", interests=(), **kw):
    return Buddy.objects.create(employee_id=eid, name=name, email=f"{eid}@x.com", department="Sales",
                                location=location, interests=list(interests), **kw)


def joiner(cid, name, location="Pune", interests=(), **kw):
    return Joiner.objects.create(candidate_id=cid, name=name, personal_email=f"{cid}@x.com", department="HR",
                                 location=location, date_of_joining=SOON, interests=list(interests), **kw)


class ClubTests(TestCase):
    def setUp(self):
        buddy("E1", "Ravi Rao", interests=["Badminton", "Books"])
        buddy("E2", "Anita Desai", interests=["Badminton"])
        buddy("E3", "Om Patil", location="Mumbai", interests=["Badminton"])
        buddy("E4", "Gone Away", interests=["Badminton"], pool_status=Buddy.PoolStatus.REMOVED)
        self.neha = joiner("C1", "Neha Joshi", interests=["Badminton", "Cooking"])
        joiner("C2", "Closed One", interests=["Badminton"], compass_status=Joiner.Status.CLOSED)

    def test_one_club_per_interest_and_location_biggest_first(self):
        clubs = {(c["interest"], c["location"]): c for c in all_clubs()}
        pune = clubs[("Badminton", "Pune")]
        self.assertEqual([b["name"] for b in pune["buddies"]], ["Anita Desai", "Ravi Rao"])  # not the removed one
        self.assertEqual([j["name"] for j in pune["joiners"]], ["Neha Joshi"])  # not the closed one
        self.assertEqual(len(clubs[("Badminton", "Mumbai")]["buddies"]), 1)
        self.assertEqual(all_clubs()[0]["interest"], "Badminton")  # 3 members: the biggest
        self.assertIn(("Cooking", "Pune"), clubs)  # a joiner alone still makes a club

    def test_filters(self):
        self.assertEqual({c["location"] for c in all_clubs(location="Mumbai")}, {"Mumbai"})
        self.assertEqual({c["interest"] for c in all_clubs(interest="Books")}, {"Books"})

    def test_the_joiners_clubs_list_the_buddies_at_their_location(self):
        clubs = clubs_for(self.neha)
        self.assertEqual([c["interest"] for c in clubs], ["Badminton", "Cooking"])
        self.assertEqual([b["name"] for b in clubs[0]["buddies"]], ["Anita Desai", "Ravi Rao"])  # Pune only
        self.assertEqual(clubs[1]["buddies"], [])


class ClubsApiTests(APITestCase):
    def setUp(self):
        self.ravi = buddy("E1", "Ravi Rao", interests=["Badminton"])
        self.ravi.password = "buddypass"
        self.ravi.set_login_code("buddypass")
        self.ravi.save()
        self.neha = joiner("C1", "Neha Joshi", interests=["Badminton"])

    def test_admins_see_clubs(self):
        self.client.force_login(get_user_model().objects.create_user("pa", is_staff=True))
        data = self.client.get("/api/hr/clubs/").data
        self.assertEqual(data["clubs"][0]["interest"], "Badminton")
        self.assertIn("Pune", data["locations"])
        self.assertEqual(self.client.get("/api/hr/clubs/?location=Mumbai").data["clubs"], [])

    def test_only_admins_see_clubs(self):
        self.assertIn(self.client.get("/api/hr/clubs/").status_code, (401, 403))

    def test_a_buddy_picks_hobbies_in_their_portal(self):
        self.client.post("/api/auth/login/", {"username": "E1", "password": "buddypass"}, format="json")
        me = self.client.get("/api/portal/me/").data
        self.assertEqual(me["interests"]["selected"], ["Badminton"])
        r = self.client.post("/api/portal/interests/", {"selected": ["Music", "Books"], "other": "Chess"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["interests"]["selected"], ["Books", "Music"])
        self.assertNotIn("clubs", r.data)  # clubs are shown to joiners

    def test_a_joiner_sees_the_buddies_in_their_clubs(self):
        self.neha.password = "joinerpass"
        self.neha.set_login_code("joinerpass")
        self.neha.save()
        self.client.post("/api/auth/login/", {"username": "C1", "password": "joinerpass"}, format="json")
        clubs = self.client.get("/api/portal/me/").data["clubs"]
        self.assertEqual(clubs, [{"interest": "Badminton", "location": "Pune",
                                  "buddies": [{"name": "Ravi Rao", "department": "Sales"}]}])
        r = self.client.post("/api/portal/interests/", {"selected": ["Cooking"]}, format="json")
        self.assertEqual(r.data["clubs"], [{"interest": "Cooking", "location": "Pune", "buddies": []}])

    def test_a_buddy_sees_the_new_joiners_in_their_clubs(self):
        self.client.post("/api/auth/login/", {"username": "E1", "password": "buddypass"}, format="json")
        clubs = self.client.get("/api/portal/me/").data["clubs"]
        self.assertEqual(clubs, [{"interest": "Badminton", "location": "Pune",
                                  "joiners": [{"name": "Neha Joshi", "department": "HR", "date_of_joining": SOON}]}])


class RetakeTests(APITestCase):
    def setUp(self):
        from .testing import make_question_set
        from .models import QuestionSet, Response
        make_question_set()
        self.ravi = buddy("E1", "Ravi Rao")
        self.ravi.password = "buddypass"
        self.ravi.set_login_code("buddypass")
        self.ravi.save()
        self.resp = Response.submitted(self.ravi, QuestionSet.active(), [3, 3, 3, 3, 3])
        self.resp.save()
        self.client.post("/api/auth/login/", {"username": "E1", "password": "buddypass"}, format="json")

    def test_a_buddy_reopens_their_profile_to_update_it(self):
        r = self.client.post("/api/portal/retake/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["link"], f"/assess/buddy/{self.ravi.token}")
        self.resp.refresh_from_db()
        self.assertIsNone(self.resp.submitted_at)  # left out of new matches until they submit again
        self.assertEqual(self.resp.answers(), [3, 3, 3, 3, 3])  # answers kept, to edit
        self.assertEqual(self.client.post("/api/portal/retake/").status_code, 400)  # not complete now

    def test_joiners_cannot_use_it(self):
        neha = joiner("C1", "Neha Joshi", password="joinerpass")
        neha.set_login_code("joinerpass")
        neha.save()
        self.client.post("/api/auth/login/", {"username": "C1", "password": "joinerpass"}, format="json")
        self.assertEqual(self.client.post("/api/portal/retake/").status_code, 403)
