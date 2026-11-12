from datetime import date, timedelta

from django.core import mail
from django.test import TestCase

from compass_app.models import Buddy, Joiner, Pairing

from . import jobs
from .models import Feedback

START = date(2026, 12, 1)


class ReviewAndCloseTests(TestCase):
    def setUp(self):
        self.joiner = Joiner.objects.create(
            name="Yash Chavan", candidate_id="C001", personal_email="yash@x.com", department="Sales",
            location="Mumbai", date_of_joining=START, compass_status=Joiner.Status.PAIRED,
        )
        self.buddy = Buddy.objects.create(
            employee_id="B", name="Bharat Mehta", email="b@x.com", department="Sales", location="Mumbai",
            pool_status=Buddy.PoolStatus.ACTIVE, total_joiners_buddied=1, active_joiners=1,
        )
        start, end = Pairing.dates_for(self.joiner)
        self.pairing = Pairing.objects.create(
            joiner=self.joiner, buddy=self.buddy, source=Pairing.Source.SYSTEM, start_date=start, end_date=end,
        )

    def day(self, n):
        return START + timedelta(days=n - 1)

    def test_pairing_is_day_1_to_day_30(self):
        self.assertEqual((self.pairing.start_date, self.pairing.end_date), (self.day(1), self.day(30)))
        self.assertEqual(self.pairing.review_opens_on(), self.day(29))

    def test_review_email_goes_once_after_the_4_weeks(self):
        self.assertEqual(jobs.send_review_requests(self.day(28)), 0)
        self.assertEqual(jobs.send_review_requests(self.day(29)), 1)
        self.assertEqual(jobs.send_review_requests(self.day(30)), 0)
        self.assertEqual(mail.outbox[0].to, ["yash@x.com"])
        self.assertIn("/login", mail.outbox[0].body)

    def test_no_review_email_once_reviewed(self):
        Feedback.objects.create(pairing=self.pairing, q1=5, q2=5, q3=5)
        self.assertEqual(jobs.send_review_requests(self.day(29)), 0)

    def test_pairing_closes_after_day_30(self):
        self.assertEqual(jobs.close_finished_pairings(self.day(30)), 0)
        self.assertEqual(jobs.close_finished_pairings(self.day(31)), 1)
        self.pairing.refresh_from_db()
        self.joiner.refresh_from_db()
        self.buddy.refresh_from_db()
        self.assertEqual((self.pairing.status, self.joiner.compass_status), (Pairing.Status.CLOSED, Joiner.Status.CLOSED))
        self.assertEqual((self.buddy.active_joiners, self.buddy.total_joiners_buddied), (0, 1))
