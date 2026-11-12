"""The audit log reads as plain sentences with names, and lists what changed in words."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from compass_app.models import AuditLog, Buddy, Joiner


class AuditWordsTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("pa", is_staff=True)
        self.client.force_login(self.admin)
        self.buddy = Buddy.objects.create(employee_id="E1", name="Anita Desai", email="a@x.com",
                                          department="Sales", location="Mumbai")
        self.joiner = Joiner.objects.create(candidate_id="C1", name="Neha Joshi", personal_email="n@x.com",
                                            department="Sales", location="Mumbai",
                                            date_of_joining=date.today() + timedelta(days=20))

    def rows(self):
        return self.client.get("/api/hr/audit/").data

    def test_a_buddy_change_reads_as_a_sentence_with_the_change_in_words(self):
        AuditLog.record("buddy_resume", self.buddy, user=self.admin,
                        before={"pool_status": "PAUSED"}, after={"pool_status": "ACTIVE"})
        row = self.rows()[0]
        self.assertEqual(row["sentence"], "{who} resumed buddy {target}")
        self.assertEqual((row["who"], row["target"], row["target_link"]), ("pa", "Anita Desai", f"/hr/buddies?buddy={self.buddy.pk}"))
        self.assertEqual(row["changes"], [{"label": "Pool status", "before": "Paused", "after": "Active"}])
        self.assertNotIn("before", row)  # no raw data on the page

    def test_buddy_ids_become_names_and_ids_are_hidden(self):
        AuditLog.record("buddy_assigned", self.joiner, user=self.admin,
                        before={"status": "AWAITING_PAIRING", "buddy": None},
                        after={"pairing_id": 9, "buddy": self.buddy.pk, "source": "SYSTEM", "reason": ""})
        row = self.rows()[0]
        self.assertEqual(row["target"], "Neha Joshi")
        self.assertEqual(row["changes"], [
            {"label": "Buddy", "before": None, "after": "Anita Desai"},
            {"label": "Chosen by", "before": None, "after": "COMPASS's top suggestion"},
        ])

    def test_what_compass_and_the_joiner_did_themselves(self):
        AuditLog.record("match_run", self.joiner, after={"run_id": 1, "tier_reached": "2"})
        AuditLog.record("attendance_confirmed", self.joiner)
        confirmed, match = self.rows()
        self.assertEqual((confirmed["who"], confirmed["sentence"]), ("Neha Joshi", "{who} confirmed they'll be there on Day 1"))
        self.assertEqual(match["who"], "COMPASS")
        self.assertEqual(match["changes"][0]["after"], "Tier 2: same department, other locations")

    def test_a_removed_record_still_reads_well(self):
        AuditLog.record("joiner_hold", self.joiner, user=self.admin)
        self.joiner.delete()
        row = self.rows()[0]
        self.assertEqual((row["target"], row["target_link"]), ("a joiner no longer in COMPASS", None))
