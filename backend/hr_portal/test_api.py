from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from compass_app.matching import run_match_for_joiner
from compass_app.models import Buddy, Joiner, Pairing, Response
from compass_app.testing import J, WORKED, make_question_set

User = get_user_model()


class HrApiTests(APITestCase):
    def setUp(self):
        self.qs = make_question_set()
        self.user = User.objects.create_user("hr", password="pw", is_staff=True)
        self.joiner = Joiner.objects.create(
            name="Yash Chavan", candidate_id="C001", personal_email="y@x.com",
            department="Sales", location="Mumbai",
            date_of_joining=date.today() + timedelta(days=10),
        )
        Response.submitted(self.joiner, self.qs, J).save()
        for key, a in WORKED.items():
            buddy = Buddy.objects.create(
                employee_id=key, name=f"Buddy {key}", email=f"{key}@x.com",
                department="Sales", location="Mumbai", pool_status=Buddy.PoolStatus.ACTIVE,
            )
            Response.submitted(buddy, self.qs, a).save()
        run_match_for_joiner(self.joiner)
        self.client.force_login(self.user)

    def confirm(self, buddy_id, **extra):
        return self.client.post(
            f"/api/hr/joiners/{self.joiner.pk}/assign/",
            {"buddy_id": buddy_id, **extra}, format="json",
        )

    def test_requires_staff_login(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/hr/joiners/").status_code, 403)

    def test_login_rejects_wrong_password_and_accepts_staff(self):
        self.client.logout()
        bad = self.client.post("/api/auth/login/", {"username": "hr", "password": "nope"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post("/api/auth/login/", {"username": "hr", "password": "pw"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.get("/api/hr/auth/me/").status_code, 200)

    def test_queue_lists_joiner_with_best_band(self):
        rows = self.client.get("/api/hr/joiners/").data
        self.assertEqual(rows[0]["best_band"], "Strong")
        self.assertEqual(rows[0]["tier_reached"], "1")

    def test_detail_has_answers_and_ranked_candidates(self):
        data = self.client.get(f"/api/hr/joiners/{self.joiner.pk}/").data
        self.assertEqual(len(data["answers"]), 5)
        self.assertEqual(data["answers"][0]["label"], "e")
        self.assertEqual([c["buddy_id"] for c in data["run"]["shown"]], ["B", "C", "E"])

    def test_top_pick_needs_no_reason_and_is_active_at_once(self):
        self.assertEqual(self.confirm("B").status_code, 200)
        pairing = Pairing.objects.get(joiner=self.joiner)
        self.assertEqual((pairing.source, pairing.status), (Pairing.Source.SYSTEM, Pairing.Status.ACTIVE))
        self.assertEqual(pairing.assigned_by, self.user)
        self.assertEqual(pairing.start_date, self.joiner.date_of_joining)
        self.assertEqual((pairing.end_date - pairing.start_date).days, 29)  # Day 1 to Day 30
        self.joiner.refresh_from_db()
        self.assertEqual(self.joiner.compass_status, Joiner.Status.PAIRED)
        b = Buddy.objects.get(employee_id="B")
        self.assertEqual((b.active_joiners, b.total_joiners_buddied), (1, 1))

    def test_only_the_buddy_is_told(self):
        self.confirm("B")
        subjects = {m.to[0]: m.subject for m in mail.outbox}
        self.assertIn("COMPASS buddy", subjects["B@x.com"])
        self.assertNotIn("y@x.com", subjects)  # the joiner sees their buddy in the Day 1 emails

    def test_not_top_pick_needs_a_reason(self):
        self.assertEqual(self.confirm("C").status_code, 400)
        self.assertEqual(self.confirm("C", reason="Buddy capacity").status_code, 200)
        pairing = Pairing.objects.get(joiner=self.joiner)
        self.assertEqual(pairing.source, Pairing.Source.SYSTEM_OVERRIDE)
        self.assertEqual(pairing.override_reason, "Buddy capacity")
        self.assertEqual(pairing.system_top_pick.employee_id, "B")

    def test_red_flag_buddy_needs_a_reason(self):
        self.assertEqual(self.confirm("D").status_code, 400)
        self.assertEqual(self.confirm("D", reason="Manager request").status_code, 200)

    def test_reason_other_needs_a_note(self):
        self.assertEqual(self.confirm("C", reason="Other").status_code, 400)
        self.assertEqual(self.confirm("C", reason="Other", note="Same city").status_code, 200)
        self.assertEqual(Pairing.objects.get(joiner=self.joiner).override_reason, "Other: Same city")

    def test_invalid_reason_rejected(self):
        self.assertEqual(self.confirm("C", reason="Because").status_code, 400)

    def test_manual_choice_of_not_suggested_buddy(self):
        self.assertEqual(self.confirm("A").status_code, 400)
        self.assertEqual(self.confirm("A", reason="Prior relationship").status_code, 200)
        pairing = Pairing.objects.get(joiner=self.joiner)
        self.assertEqual(pairing.source, Pairing.Source.MANUAL)
        self.assertEqual(pairing.band, "Not suggested")

    def test_buddy_can_be_changed_within_two_days_only(self):
        self.assertEqual(self.confirm("B").status_code, 200)
        self.assertEqual(self.confirm("B").status_code, 400)  # already their buddy
        self.assertEqual(self.confirm("C", reason="Buddy capacity").status_code, 200)
        old = Pairing.objects.get(joiner=self.joiner, buddy__employee_id="B")
        self.assertEqual(old.status, Pairing.Status.CANCELLED)
        self.assertEqual(Buddy.objects.get(employee_id="B").active_joiners, 0)
        self.assertEqual(Buddy.objects.get(employee_id="C").active_joiners, 1)
        self.assertTrue(any("no longer" in m.subject for m in mail.outbox if m.to == ["B@x.com"]))

        Pairing.objects.filter(status=Pairing.Status.ACTIVE).update(assigned_at=timezone.now() - timedelta(days=3))
        self.assertEqual(self.confirm("E", reason="Buddy capacity").status_code, 400)

    def test_ineligible_buddy_rejected(self):
        Buddy.objects.create(
            employee_id="Z", name="Zed", email="z@x.com", department="Sales",
            location="Mumbai", pool_status=Buddy.PoolStatus.PAUSED,
        )
        self.assertEqual(self.confirm("Z", reason="Buddy capacity").status_code, 400)