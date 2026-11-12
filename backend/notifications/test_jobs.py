from datetime import date, timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from compass_app.matching import run_match_for_joiner
from compass_app.models import Buddy, Joiner, Pairing, Response
from compass_app.testing import make_question_set

from . import emails, jobs
from .models import Notification

TODAY = date(2026, 11, 2)
J = [5, 4, 5, 4, 5]


def make_joiner(days_ahead, status=Joiner.Status.AWAITING_ASSESSMENT, candidate_id="C001", **kw):
    return Joiner.objects.create(
        name="Yash Chavan", candidate_id=candidate_id, personal_email=f"{candidate_id}@x.com",
        department="Sales", location="Mumbai", compass_status=status,
        date_of_joining=TODAY + timedelta(days=days_ahead), **kw,
    )


class JoinerEmailTests(TestCase):
    """The quiz is asked in the login email (see test_prejoining); no automatic reminders."""

    def test_overdue_joiner_goes_to_manual_and_the_admins_are_told(self):
        joiner = make_joiner(7)
        self.assertEqual(jobs.route_overdue_to_manual(TODAY), 0)  # day -7 is the last day to answer
        joiner.date_of_joining -= timedelta(days=1)
        joiner.save()
        self.assertEqual(jobs.route_overdue_to_manual(TODAY), 1)
        joiner.refresh_from_db()
        self.assertEqual(joiner.compass_status, Joiner.Status.MANUAL)
        self.assertEqual(mail.outbox[0].to, ["compass-admin@united-group.local"])
        self.assertEqual(jobs.route_overdue_to_manual(TODAY), 0)

    def test_joiner_who_submitted_gets_nothing(self):
        make_joiner(1, status=Joiner.Status.AWAITING_PAIRING)
        for day in range(0, 8):
            jobs.run_all(TODAY - timedelta(days=day))
        self.assertEqual(len(mail.outbox), 0)


class BuddyReminderTests(TestCase):
    def setUp(self):
        self.qs = make_question_set()
        self.buddy = Buddy.objects.create(
            employee_id="E1", name="Ravi Rao", email="ravi@x.com", department="Sales", location="Mumbai",
        )
        self.added = self.buddy.date_added_to_pool

    def test_reminders_weekly_max_three(self):
        results = [jobs.send_buddy_reminders(self.added + timedelta(days=d)) for d in (0, 4, 5, 11, 12, 19, 26, 40)]
        self.assertEqual(results, [0, 0, 1, 0, 1, 1, 0, 0])
        self.assertIn("E1", mail.outbox[0].body)

    def test_no_reminders_once_profile_is_done(self):
        Response.submitted(self.buddy, self.qs, [1, 1, 1, 1, 1]).save()
        self.assertEqual(jobs.send_buddy_reminders(self.added + timedelta(days=20)), 0)


class AssignmentEmailTests(TestCase):
    def setUp(self):
        self.qs = make_question_set()
        self.joiner = make_joiner(10, designation="Analyst")
        self.buddy = Buddy.objects.create(
            employee_id="E1", name="Ravi Rao", email="ravi@x.com", department="Sales",
            location="Mumbai", designation="Manager", intro="Happy to help.",
        )
        start, end = Pairing.dates_for(self.joiner)
        self.pairing = Pairing.objects.create(
            joiner=self.joiner, buddy=self.buddy, source=Pairing.Source.SYSTEM, start_date=start, end_date=end,
        )

    def test_only_the_buddy_is_emailed_when_assigned(self):
        emails.send_assignment(self.pairing)
        self.assertEqual([m.to for m in mail.outbox], [["ravi@x.com"]])  # the joiner sees it in Day 1 emails
        self.assertIn("assigned as the COMPASS buddy for Yash Chavan", mail.outbox[0].body)
        self.assertNotIn("accept", mail.outbox[0].body.lower())  # nobody is asked, the buddy is told
        emails.send_assignment(self.pairing)
        self.assertEqual(len(mail.outbox), 1)  # once only

    def test_the_admins_are_alerted_when_no_good_match_exists(self):
        Response.submitted(self.joiner, self.qs, [5, 4, 5, 4, 5]).save()
        run_match_for_joiner(self.joiner)
        self.assertTrue(any("No Strong or Good match" in m.subject for m in mail.outbox))


class RunDailyTests(TestCase):
    def test_command_runs_and_is_repeatable(self):
        make_joiner(14, added_on=TODAY - timedelta(days=10))
        call_command("run_daily", "--today", "2026-11-02", stdout=StringIO())
        call_command("run_daily", "--today", "2026-11-02", stdout=StringIO())
        self.assertEqual(sorted(Notification.objects.values_list("kind", flat=True)), ["our_story", "welcome"])
        self.assertEqual(len(mail.outbox), 2)
