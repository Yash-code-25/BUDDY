from datetime import date, timedelta

from rest_framework.test import APITestCase

from .models import Buddy, Joiner, Response
from .testing import make_question_set


class AssessmentApiTests(APITestCase):
    def setUp(self):
        self.qs = make_question_set()
        self.joiner = Joiner.objects.create(
            name="Priya Sharma", candidate_id="C1", personal_email="p@x.com",
            department="Sales", location="Mumbai",
            date_of_joining=date.today() + timedelta(days=7),
        )
        self.buddy = Buddy.objects.create(
            name="Ravi Rao", employee_id="E1", email="r@x.com",
            department="Sales", location="Mumbai",
        )

    def url(self, kind, token, tail=""):
        return f"/api/assessment/{kind}/{token}/{tail}"

    def answer(self, kind, token, question, value):
        return self.client.post(self.url(kind, token, "answer/"),
                                {"question": question, "value": value}, format="json")

    def answer_all(self, kind, token):
        for n in range(1, 6):
            self.answer(kind, token, n, 3)

    def test_quiz_link_works_for_one_week_after_it_is_sent(self):
        url = self.url("joiner", self.joiner.token)
        Joiner.objects.filter(pk=self.joiner.pk).update(quiz_link_sent_on=date.today() - timedelta(days=7))
        self.assertEqual(self.client.get(url).status_code, 200)
        Joiner.objects.filter(pk=self.joiner.pk).update(quiz_link_sent_on=date.today() - timedelta(days=8))
        self.assertEqual(self.client.get(url).status_code, 410)
        self.assertEqual(self.answer("joiner", self.joiner.token, 1, 3).status_code, 410)

    def test_after_submitting_the_link_still_shows_their_page(self):
        self.answer_all("joiner", self.joiner.token)
        self.client.post(self.url("joiner", self.joiner.token, "submit/"), {}, format="json")
        Joiner.objects.filter(pk=self.joiner.pk).update(quiz_link_sent_on=date.today() - timedelta(days=30))
        self.assertEqual(self.client.get(self.url("joiner", self.joiner.token)).status_code, 200)

    def test_get_returns_questions_with_labels(self):
        r = self.client.get(self.url("joiner", self.joiner.token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["first_name"], "Priya")
        self.assertEqual(r.data["status"], "not_started")
        self.assertEqual(len(r.data["questions"]), 5)
        self.assertEqual(len(r.data["questions"][0]["options"]), 5)

    def test_answer_autosaves_and_resumes(self):
        self.assertEqual(self.answer("joiner", self.joiner.token, 1, 4).status_code, 200)
        r = self.client.get(self.url("joiner", self.joiner.token))
        self.assertEqual(r.data["status"], "in_progress")
        self.assertEqual(r.data["answers"], {"1": 4})
        self.qs.refresh_from_db()
        self.assertTrue(self.qs.is_locked)

    def test_invalid_answers_rejected(self):
        self.assertEqual(self.answer("joiner", self.joiner.token, 1, 6).status_code, 400)
        self.assertEqual(self.answer("joiner", self.joiner.token, 9, 3).status_code, 400)

    def test_cannot_submit_incomplete(self):
        self.answer("joiner", self.joiner.token, 1, 3)
        r = self.client.post(self.url("joiner", self.joiner.token, "submit/"))
        self.assertEqual(r.status_code, 400)

    def test_joiner_submit_saves_response_and_routes_status(self):
        self.answer_all("joiner", self.joiner.token)
        r = self.client.post(self.url("joiner", self.joiner.token, "submit/"))
        self.assertEqual(r.status_code, 200)
        self.joiner.refresh_from_db()
        # No active buddies exist in this test, so the match run sends the joiner to manual.
        self.assertEqual(self.joiner.compass_status, Joiner.Status.MANUAL)
        self.assertIsNotNone(Response.objects.get(joiner=self.joiner).submitted_at)
        
    def test_cannot_edit_or_resubmit_after_submit(self):
        self.answer_all("joiner", self.joiner.token)
        self.client.post(self.url("joiner", self.joiner.token, "submit/"))
        self.assertEqual(self.answer("joiner", self.joiner.token, 1, 5).status_code, 400)
        self.assertEqual(
            self.client.post(self.url("joiner", self.joiner.token, "submit/")).status_code, 400)
        self.assertEqual(
            self.client.get(self.url("joiner", self.joiner.token)).data["status"], "submitted")

    def test_buddy_submit_activates_buddy(self):
        self.assertEqual(self.buddy.pool_status, Buddy.PoolStatus.PAUSED)
        self.answer_all("buddy", self.buddy.token)
        self.client.post(self.url("buddy", self.buddy.token, "submit/"))
        self.buddy.refresh_from_db()
        self.assertEqual(self.buddy.pool_status, Buddy.PoolStatus.ACTIVE)

    def test_expired_joiner_link(self):
        self.joiner.date_of_joining = date.today() - timedelta(days=1)
        self.joiner.save()
        self.assertEqual(self.client.get(self.url("joiner", self.joiner.token)).status_code, 410)

    def test_unknown_token_is_404(self):
        self.assertEqual(
            self.client.get(self.url("joiner", "11111111-1111-1111-1111-111111111111")).status_code, 404)

    def test_boolean_answer_is_rejected(self):
        r = self.client.post(self.url("joiner", self.joiner.token, "answer/"),
                             {"question": True, "value": 3}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_submitting_keeps_a_joiner_on_hold(self):
        Joiner.objects.filter(pk=self.joiner.pk).update(compass_status=Joiner.Status.ON_HOLD)
        self.answer_all("joiner", self.joiner.token)
        self.client.post(self.url("joiner", self.joiner.token, "submit/"), {}, format="json")
        self.joiner.refresh_from_db()
        self.assertEqual(self.joiner.compass_status, Joiner.Status.ON_HOLD)
