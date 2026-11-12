from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from feedback.models import Feedback
from notifications.models import Notification

from .models import Buddy, InductionItem, InductionTick, Joiner, MatchRun, Pairing, Response


class SeedDemoTests(TestCase):
    def seed(self, buddies=8, joiners=8):
        out = StringIO()
        call_command("seed_demo", "--buddies", str(buddies), "--joiners", str(joiners), stdout=out)
        return out.getvalue()

    def test_builds_buddies_joiners_and_an_induction_programme(self):
        self.seed()
        self.assertEqual((Buddy.objects.count(), Joiner.objects.count()), (8, 8))
        self.assertEqual(set(InductionItem.objects.values_list("week", flat=True)), {1, 2, 3, 4})

    def test_every_joiner_still_has_to_answer_and_nobody_is_assigned(self):
        self.seed()
        self.assertEqual(set(Joiner.objects.values_list("compass_status", flat=True)),
                         {Joiner.Status.AWAITING_ASSESSMENT})
        self.assertFalse(Response.objects.filter(assessment_code=Response.Code.JOINER).exists())
        for model in (Pairing, MatchRun, InductionTick, Feedback):
            self.assertFalse(model.objects.exists(), model)

    def test_buddies_are_ready_to_be_matched_with_no_history(self):
        self.seed()
        self.assertEqual(Response.objects.filter(assessment_code=Response.Code.BUDDY, submitted_at__isnull=False).count(), 8)
        self.assertEqual(set(Buddy.objects.values_list("active_joiners", "total_joiners_buddied")), {(0, 0)})

    def test_everyone_can_sign_in_with_the_printed_code(self):
        output = self.seed()
        line = next(l for l in output.splitlines() if " C005 " in l)
        r = self.client.post("/api/auth/login/", {"username": "C005", "password": line.split()[-1]},
                             content_type="application/json")
        self.assertEqual(r.json()["to"], "/portal")

    def test_running_it_again_starts_fresh_and_leaves_user_accounts_alone(self):
        get_user_model().objects.create_superuser("superuser", "", "pw")
        self.seed()
        self.seed()
        self.assertEqual((Buddy.objects.count(), Joiner.objects.count()), (8, 8))
        self.assertEqual(list(get_user_model().objects.values_list("username", flat=True)), ["superuser"])

    def test_defaults_are_100_buddies_and_10_joiners(self):
        out = StringIO()
        call_command("seed_demo", stdout=out)
        self.assertEqual((Buddy.objects.count(), Joiner.objects.count()), (100, 10))
        self.assertEqual(MatchRun.objects.count(), 1)  # C009 answered, C010 has not

    def test_generated_people_fill_up_to_the_total_and_share_one_code(self):
        output = self.seed(buddies=12, joiners=28)
        self.assertEqual((Buddy.objects.count(), Joiner.objects.count()), (12, 28))
        answered = Joiner.objects.filter(compass_status__in=[Joiner.Status.AWAITING_PAIRING, Joiner.Status.MANUAL])
        self.assertTrue(answered.exists())
        self.assertEqual(MatchRun.objects.count(), answered.count())
        self.assertFalse(Pairing.objects.exists())
        self.assertFalse(Notification.objects.exists())  # no alert emails for demo data
        code = output.strip().splitlines()[-1].rstrip(".").split()[-1]
        for username in ("E009", "C009"):
            r = self.client.post("/api/auth/login/", {"username": username, "password": code},
                                 content_type="application/json")
            self.assertEqual(r.status_code, 200, username)
