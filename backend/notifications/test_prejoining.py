"""The joiner's emails: the same five for everyone before joining, then the buddy review."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APITestCase

from compass_app.models import Buddy, Joiner, Pairing, Settings
from employee_portal.views import INTERESTS

from . import jobs, prejoining
from .models import Notification
from .render import render

TODAY = date(2026, 11, 2)
FIVE = ["Welcome to United Group, Neha!", "Your COMPASS login details", "Get to know United Group before you join"]


def joiner(notice, **kw):
    """A joiner added on TODAY who joins `notice` days later."""
    return Joiner.objects.create(
        name="Neha Joshi", candidate_id="C1", personal_email="neha@x.com", department="Sales",
        location="Mumbai", date_of_joining=TODAY + timedelta(days=notice), added_on=TODAY, **kw,
    )


def add_and_run(notice):
    """Add a joiner the way the admin does, then run the daily job every day until they join.
    Returns the subjects they got each day."""
    from hr_portal.people import welcome

    person = joiner(notice)
    days = []
    for d in range(notice + 1):
        before = len(mail.outbox)
        if d == 0:
            welcome(person, "joiner", TODAY)
        jobs.run_all(TODAY + timedelta(days=d))
        days.append([m.subject for m in mail.outbox[before:] if m.to == ["neha@x.com"]])
    return person, days


class FiveEmailTests(TestCase):
    def test_early_joiner_gets_the_five_on_their_days(self):
        person, days = add_and_run(30)
        self.assertEqual(days[0], ["Welcome to United Group, Neha!", "Your COMPASS login details"])
        self.assertEqual(days[16], ["Get to know United Group before you join"])  # 14 days before
        self.assertEqual(days[27], ["Everything you need for Wednesday, 2 December 2026"])  # 3 days before
        self.assertEqual(days[29], ["See you tomorrow, Neha!"])  # 1 day before
        self.assertEqual(sum(map(len, days)), 5)  # nothing else: no quiz email, no reminders

    def test_late_joiner_gets_the_same_five(self):
        person, days = add_and_run(5)
        self.assertEqual(days[0], ["Welcome to United Group, Neha!", "Your COMPASS login details"])
        self.assertEqual(days[1], ["Get to know United Group before you join"])  # the day after being added
        self.assertEqual(days[2], ["Everything you need for Saturday, 7 November 2026"])  # 3 days before
        self.assertEqual(days[4], ["See you tomorrow, Neha!"])
        self.assertEqual(sum(map(len, days)), 5)

    def test_a_joiner_added_the_day_before_still_gets_all_five(self):
        person, days = add_and_run(1)
        self.assertEqual(len(days[0]), 5)

    def test_the_login_email_asks_the_questions_with_a_due_date(self):
        add_and_run(30)
        login = next(m for m in mail.outbox if m.subject == "Your COMPASS login details")
        person = Joiner.objects.get(candidate_id="C1")
        self.assertIn("Username: C1", login.body)
        self.assertIn(f"Password: {person.password}", login.body)
        self.assertIn("help us find your buddy", login.body)
        self.assertIn("Please complete it by Wednesday, 25 November 2026", login.body)  # 7 days before joining

    def test_late_joiners_have_2_days_to_answer_then_manual_pairing(self):
        person, days = add_and_run(8)
        login = next(m for m in mail.outbox if m.subject == "Your COMPASS login details")
        self.assertIn("Please complete it by Wednesday, 4 November 2026", login.body)
        person.refresh_from_db()
        self.assertEqual(person.compass_status, Joiner.Status.MANUAL)

    def test_no_questions_in_the_login_email_once_answered(self):
        person = joiner(30, compass_status=Joiner.Status.AWAITING_PAIRING)
        from employee_portal.credentials import issue_login
        issue_login(person, "joiner")
        self.assertNotIn("help us find your buddy", mail.outbox[-1].body)

    def test_the_company_email_has_the_story_and_handbook(self):
        s = Settings.load()
        s.story_video_link, s.handbook_link = "https://v.example/story", "https://h.example/book"
        s.save()
        prejoining.company(joiner(30), s, TODAY)
        html = mail.outbox[-1].alternatives[0][0]
        for text in ("Watch our story", "https://v.example/story", "Open the handbook", "https://h.example/book",
                     "What we stand for"):
            self.assertIn(text, html)

    def test_a_joiner_added_before_the_series_existed_gets_none_of_it(self):
        person = joiner(20)
        person.added_on = None
        person.save()
        self.assertEqual(prejoining.send_all_due(TODAY), 0)


class ContentTests(TestCase):
    def test_blank_details_leave_their_lines_out_and_filled_ones_show(self):
        person = joiner(20)
        prejoining.day_one(person, Settings.load(), TODAY)
        body = mail.outbox[-1].body
        self.assertNotIn("Time:", body)
        self.assertNotIn("Address:", body)
        self.assertNotIn("call us on", body)

        s = Settings.load()
        s.contact_phone = "+91 22 1234 5678"
        # The office comes from Settings by location: Neha is in Mumbai, so Pune's never shows.
        s.office_details = {"Mumbai": {"address": "United House, Pune", "map_link": "https://maps.example/m"},
                            "Pune": {"address": "Somewhere else"}}
        s.save()
        person.reporting_time, person.contact_person = "9:30 am", "Anita"
        person.manager_name = "Rahul Mehta"
        person.save()
        mail.outbox.clear()
        Notification.objects.all().delete()
        prejoining.send_due(person, person.date_of_joining - timedelta(days=1))
        logistics = next(m.body for m in mail.outbox if m.subject.startswith("Everything you need"))
        for text in ("Time: please arrive by 9:30 am", "Address: United House, Pune", "Ask for: Anita",
                     "call us on +91 22 1234 5678", "Yes, I'll be there"):
            self.assertIn(text, logistics)
        tomorrow = next(m.body for m in mail.outbox if m.subject.startswith("See you tomorrow"))
        self.assertIn("Rahul Mehta, your manager", tomorrow)
        self.assertIn("please arrive by 9:30 am at United House, Pune", tomorrow)
        self.assertNotIn("Your buddy", tomorrow)  # none assigned yet

    def test_see_you_tomorrow_names_the_buddy(self):
        person = joiner(20)
        buddy = Buddy.objects.create(employee_id="E1", name="Ravi Rao", email="r@x.com", department="Sales",
                                     location="Mumbai")
        start, end = Pairing.dates_for(person)
        Pairing.objects.create(joiner=person, buddy=buddy, source=Pairing.Source.SYSTEM, start_date=start, end_date=end)
        prejoining.see_you_tomorrow(person, Settings.load(), TODAY)
        self.assertIn("Your buddy, Ravi Rao, will be around too", mail.outbox[-1].body)

    def test_every_email_is_formatted_from_team_united(self):
        prejoining.welcome(joiner(20), Settings.load(), TODAY)
        email = mail.outbox[-1]
        self.assertTrue(email.from_email.startswith("Team United"))
        html = email.alternatives[0][0]
        self.assertIn("<li", html)
        self.assertTrue(email.body.rstrip().endswith("Welcome aboard,\nTeam United\nUnited Group"))


class RenderTests(TestCase):
    def test_markup(self):
        text, html = render("## Heading\nLine\n• one\n• two\n\n[[Go|https://x.y/z]]\n\nA [link](https://a.b) and **bold**")
        self.assertIn("Heading", text)
        self.assertIn("Go: https://x.y/z", text)
        self.assertIn("A link (https://a.b) and bold", text)
        self.assertIn("<h3", html)
        self.assertIn("<ul", html)
        self.assertIn('href="https://x.y/z"', html)
        self.assertIn("<strong>bold</strong>", html)

    def test_text_is_escaped_in_html(self):
        self.assertIn("&lt;script&gt;", render("<script>")[1])


class AddJoinerTests(APITestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("pa", is_staff=True))

    def test_adding_a_joiner_sends_the_welcome_then_the_login_details(self):
        r = self.client.post("/api/hr/joiners/", {
            "candidate_id": "C900", "name": "Neha Joshi", "personal_email": "neha@x.com", "department": "Sales",
            "location": "Mumbai", "date_of_joining": str(date.today() + timedelta(days=30)),
            "manager_name": "Rahul Mehta",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual([m.subject for m in mail.outbox], ["Welcome to United Group, Neha!", "Your COMPASS login details"])
        person = Joiner.objects.get(candidate_id="C900")
        self.assertEqual((person.added_on, person.manager_name), (date.today(), "Rahul Mehta"))

    def test_the_admin_edits_day_one_details(self):
        person = joiner(20)
        r = self.client.put(f"/api/hr/joiners/{person.pk}/day-one/", {"reporting_time": " 9:30 am ", "directions": ""},
                            format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["reporting_time"], "9:30 am")
        r = self.client.put(f"/api/hr/joiners/{person.pk}/day-one/", {"manager_name": "x" * 200}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_settings_keep_the_email_details(self):
        data = self.client.get("/api/hr/settings/").data
        self.assertEqual(data["manual_cutoff_day"], 7)
        data.update(story_video_link="https://v.example/story", contact_phone="+91 1")
        r = self.client.put("/api/hr/settings/", data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["story_video_link"], r.data["contact_phone"]), ("https://v.example/story", "+91 1"))

    def test_office_details_are_kept_per_location(self):
        data = self.client.get("/api/hr/settings/").data
        data["office_details"] = {
            "Pune": {"address": " United House, Baner ", "map_link": "https://maps.example/p"},
            "Mumbai": {"address": "", "map_link": ""},  # blank: not kept
            "Atlantis": {"address": "Nowhere"},  # not on the locations list: dropped
        }
        r = self.client.put("/api/hr/settings/", data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["office_details"],
                         {"Pune": {"address": "United House, Baner", "map_link": "https://maps.example/p"}})
        self.assertEqual(Settings.load().office_for("Mumbai"), {"address": "", "map_link": ""})


class PortalTests(APITestCase):
    def setUp(self):
        self.person = Joiner.objects.create(
            name="Neha Joshi", candidate_id="C1", personal_email="neha@x.com", department="Sales",
            location="Mumbai", date_of_joining=date.today() + timedelta(days=3), password="abcdefgh",
        )
        self.person.set_login_code("abcdefgh")
        self.person.save()
        self.client.post("/api/auth/login/", {"username": "C1", "password": "abcdefgh"}, format="json")

    def test_the_joiner_saves_their_interests(self):
        me = self.client.get("/api/portal/me/").data
        self.assertEqual(me["interests"]["choices"], INTERESTS)
        r = self.client.post("/api/portal/interests/", {"selected": ["Music", "Books"], "other": "Chess"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["interests"]["selected"], ["Books", "Music"])
        self.assertEqual(self.client.post("/api/portal/interests/", {"selected": ["Skydiving"]}, format="json").status_code, 400)

    def test_yes_ill_be_there(self):
        me = self.client.get("/api/portal/me/").data
        self.assertEqual((me["day_one"]["show"], me["day_one"]["confirmed"]), (True, False))
        self.assertTrue(self.client.post("/api/portal/attendance/").data["confirmed"])
        self.person.refresh_from_db()
        self.assertIsNotNone(self.person.attendance_confirmed_at)

    def test_the_confirm_card_waits_until_3_days_before(self):
        self.person.date_of_joining = date.today() + timedelta(days=10)
        self.person.save()
        self.assertFalse(self.client.get("/api/portal/me/").data["day_one"]["show"])
