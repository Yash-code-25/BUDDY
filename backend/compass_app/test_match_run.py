from datetime import date, timedelta

from rest_framework.test import APITestCase

from .models import Buddy, Joiner, MatchRun, Response, Settings
from .testing import J, WORKED, make_question_set


class MatchRunOnSubmitTests(APITestCase):
    def setUp(self):
        self.qs = make_question_set()
        self.joiner = Joiner.objects.create(
            name="Yash Chavan", candidate_id="C001", personal_email="y@x.com",
            department="Sales", location="Mumbai",
            date_of_joining=date.today() + timedelta(days=10),
        )

    def add_buddy(self, emp_id, answers, status=Buddy.PoolStatus.ACTIVE):
        buddy = Buddy.objects.create(
            employee_id=emp_id, name=f"Buddy {emp_id}", email=f"{emp_id}@x.com",
            department="Sales", location="Mumbai", pool_status=status,
        )
        Response.submitted(buddy, self.qs, answers).save()
        return buddy

    def add_worked_pool(self):
        return {k: self.add_buddy(k, v) for k, v in WORKED.items()}

    def take_quiz(self, answers=J):
        base = f"/api/assessment/joiner/{self.joiner.token}/"
        for n, v in enumerate(answers, start=1):
            self.client.post(base + "answer/", {"question": n, "value": v}, format="json")
        return self.client.post(base + "submit/")

    def latest_run(self):
        return MatchRun.objects.filter(joiner=self.joiner).latest("run_time")

    @staticmethod
    def ids(candidates):
        return [c["buddy_id"] for c in candidates]

    def test_submit_runs_match_and_stores_snapshot(self):
        self.add_worked_pool()
        self.assertEqual(self.take_quiz().status_code, 200)
        run = self.latest_run()
        self.assertEqual(run.tier_reached, "1")
        self.assertEqual(self.ids(run.results["shown"]), ["B", "C", "E"])
        self.assertEqual(self.ids(run.results["more"]), ["D"])
        self.joiner.refresh_from_db()
        self.assertEqual(self.joiner.compass_status, Joiner.Status.AWAITING_PAIRING)

    def test_empty_pool_goes_to_manual(self):
        self.take_quiz()
        self.assertEqual(self.latest_run().tier_reached, "MANUAL")
        self.joiner.refresh_from_db()
        self.assertEqual(self.joiner.compass_status, Joiner.Status.MANUAL)

    def test_paused_buddy_is_not_scored(self):
        self.add_buddy("B", WORKED["B"], status=Buddy.PoolStatus.PAUSED)
        self.take_quiz()
        self.assertNotIn("B", self.ids(self.latest_run().results["scored"]))

    def open_page(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.get_or_create(username="pa", is_staff=True)[0])
        return self.client.get(f"/api/hr/joiners/{self.joiner.pk}/").data

    def test_a_buddy_who_finishes_later_shows_up_on_the_next_refresh(self):
        from django.core import mail
        self.take_quiz()  # nobody in the pool yet: manual, and the admins are told once
        self.assertEqual(self.latest_run().tier_reached, "MANUAL")
        self.add_buddy("B", WORKED["B"])  # finishes their profile after the joiner
        data = self.open_page()
        self.assertIn("B", self.ids(data["run"]["scored"]))
        self.assertEqual(data["joiner"]["status"], Joiner.Status.AWAITING_PAIRING)
        # Nothing changed since: the next refresh keeps the same run.
        runs = MatchRun.objects.filter(joiner=self.joiner).count()
        self.open_page()
        self.assertEqual(MatchRun.objects.filter(joiner=self.joiner).count(), runs)
        self.assertEqual(sum("No Strong or Good match" in m.subject for m in mail.outbox), 1)

    def test_a_buddy_paused_since_drops_out_and_a_paired_joiner_is_left_alone(self):
        self.add_worked_pool()
        self.take_quiz()
        Buddy.objects.filter(employee_id="B").update(pool_status=Buddy.PoolStatus.PAUSED)
        self.assertNotIn("B", self.ids(self.open_page()["run"]["scored"]))
        self.client.post(f"/api/hr/joiners/{self.joiner.pk}/assign/", {"buddy_id": "C"}, format="json")
        runs = MatchRun.objects.filter(joiner=self.joiner).count()
        Buddy.objects.filter(employee_id="B").update(pool_status=Buddy.PoolStatus.ACTIVE)
        self.open_page()
        self.assertEqual(MatchRun.objects.filter(joiner=self.joiner).count(), runs)

    def test_settings_from_database_are_used(self):
        self.add_worked_pool()
        s = Settings.load()
        s.candidates_per_tier = 1
        s.save()
        self.take_quiz()
        self.assertEqual(len(self.latest_run().results["shown"]), 1)