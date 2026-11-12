from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle

from compass_app.models import Buddy, InductionItem, Joiner, Pairing, Response
from compass_app.testing import make_question_set
from feedback.models import Feedback


def login_code(email):
    line = next(l for l in email.body.splitlines() if l.startswith("Password:"))
    return line.split(":", 1)[1].strip()


class PortalBase(APITestCase):
    def setUp(self):
        self.qs = make_question_set()
        self.joiner = Joiner.objects.create(
            name="Priya Sharma", candidate_id="C1", personal_email="p@x.com", department="Sales",
            location="Mumbai", date_of_joining=date.today() + timedelta(days=5),
        )
        self.joiner.password = "111111"
        self.joiner.set_login_code("111111")
        self.joiner.save()
        self.buddy = Buddy.objects.create(
            name="Ravi Rao", employee_id="E1", email="r@x.com", department="Sales", location="Mumbai",
            designation="Manager", intro="Happy to help.", pool_status=Buddy.PoolStatus.ACTIVE,
        )
        self.buddy.password = "222222"
        self.buddy.set_login_code("222222")
        self.buddy.save()
        Response.submitted(self.buddy, self.qs, [3, 3, 3, 3, 3]).save()
        self.items = [InductionItem.objects.create(week=w, day=f"Day {w}", activity=f"Thing {w}") for w in (1, 2, 3, 4)]

    def sign_in(self, username, code, client=None):
        return (client or self.client).post("/api/auth/login/", {"username": username, "password": code}, format="json")

    def me(self):
        return self.client.get("/api/portal/me/")

    def pair(self, joined_days_ago=0):
        self.joiner.date_of_joining = date.today() - timedelta(days=joined_days_ago)
        self.joiner.save()
        start, end = Pairing.dates_for(self.joiner)
        return Pairing.objects.create(joiner=self.joiner, buddy=self.buddy, source=Pairing.Source.SYSTEM,
                                      start_date=start, end_date=end)


class SignInTests(PortalBase):
    def test_not_signed_in_gets_403(self):
        self.assertEqual(self.me().status_code, 403)

    def test_joiner_and_buddy_sign_in_with_username_and_code(self):
        self.assertEqual(self.sign_in("C1", "000000").status_code, 400)
        self.assertEqual(self.sign_in("c1", "111111").data["to"], "/portal")
        self.assertEqual((self.me().data["kind"], self.me().data["username"]), ("joiner", "C1"))
        self.client.post("/api/portal/logout/")
        self.assertEqual(self.me().status_code, 403)
        self.assertEqual(self.sign_in("E1", "222222").data["to"], "/portal")
        self.assertEqual(self.me().data["kind"], "buddy")

    def test_admins_sign_in_on_the_same_page_and_go_to_the_admin_screens(self):
        get_user_model().objects.create_user("pa", password="admin-pass-1", is_staff=True)
        self.assertEqual(self.sign_in("pa", "admin-pass-1").data["to"], "/hr")
        self.assertEqual(self.me().status_code, 403)

    def test_portal_session_is_not_an_admin_session(self):
        self.sign_in("C1", "111111")
        self.assertEqual(self.client.get("/api/hr/joiners/").status_code, 403)

    def test_removed_buddy_cannot_sign_in(self):
        self.buddy.pool_status = Buddy.PoolStatus.REMOVED
        self.buddy.save()
        self.assertEqual(self.sign_in("E1", "222222").status_code, 400)

    def test_portal_changes_need_the_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        self.pair()
        self.sign_in("C1", "111111", client)
        r = client.post(f"/api/portal/induction/{self.items[0].pk}/", {"done": True}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_too_many_sign_in_attempts_are_slowed_down(self):
        cache.clear()
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"login": "3/minute"}):
            codes = [self.sign_in("C1", "999999").status_code for _ in range(4)]
        cache.clear()
        self.assertEqual(codes, [400, 400, 400, 429])


class LoginDetailsTests(PortalBase):
    NEW = {
        "candidate_id": "C900", "name": "Neha Kulkarni", "personal_email": "neha@x.com",
        "department": "Sales", "location": "Mumbai", "date_of_joining": "2026-12-01",
    }

    def setUp(self):
        super().setUp()
        self.admin = get_user_model().objects.create_user("pa", is_staff=True)
        self.client.force_login(self.admin)

    def test_a_new_joiner_gets_their_username_and_code_and_can_sign_in(self):
        self.assertEqual(self.client.post("/api/hr/joiners/", self.NEW, format="json").status_code, 201)
        email = next(m for m in mail.outbox if m.subject == "Your COMPASS login details")
        self.assertEqual(email.to, ["neha@x.com"])
        self.assertIn("Username: C900", email.body)
        code = login_code(email)
        self.assertRegex(code, r"^[A-Za-z2-9]{8}$")
        self.assertEqual(Joiner.objects.get(candidate_id="C900").password, code)  # kept for later emails
        self.client.logout()
        self.assertEqual(self.sign_in("C900", code).data["to"], "/portal")

    def test_a_new_buddy_gets_their_details_too(self):
        r = self.client.post("/api/hr/buddies/", {"employee_id": "E9", "name": "Om Patil", "email": "om@x.com",
                                                  "department": "Sales", "location": "Mumbai"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("Username: E9", next(m for m in mail.outbox if m.to == ["om@x.com"]).body)

    def test_send_login_details_sends_the_same_password_again(self):
        for _ in range(2):
            self.client.post(f"/api/hr/joiners/{self.joiner.pk}/action/", {"action": "send_login"}, format="json")
            self.assertEqual(login_code(mail.outbox[-1]), "111111")
        self.client.logout()
        self.assertEqual(self.sign_in("C1", "111111").status_code, 200)  # it keeps working

    def test_someone_without_a_stored_password_gets_one_once(self):
        self.joiner.password = ""
        self.joiner.save()
        self.client.post(f"/api/hr/joiners/{self.joiner.pk}/action/", {"action": "send_login"}, format="json")
        first = login_code(mail.outbox[-1])
        self.client.post(f"/api/hr/joiners/{self.joiner.pk}/action/", {"action": "send_login"}, format="json")
        self.assertEqual(login_code(mail.outbox[-1]), first)
        self.client.logout()
        self.assertEqual(self.sign_in("C1", first).status_code, 200)


class JoinerPortalTests(PortalBase):
    def setUp(self):
        super().setUp()
        self.sign_in("C1", "111111")

    def test_before_a_buddy_there_is_the_quiz_and_no_induction(self):
        me = self.me().data
        self.assertEqual(me["quiz"]["status"], "not_started")
        self.assertTrue(me["quiz"]["open"])
        self.assertIsNone(me["buddy"])
        self.assertIsNone(me["induction"])
        r = self.client.post(f"/api/portal/induction/{self.items[0].pk}/", {"done": True}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_once_assigned_the_buddy_and_the_4_week_induction_show(self):
        self.pair(joined_days_ago=8)
        me = self.me().data
        self.assertEqual(me["buddy"]["name"], "Ravi Rao")
        self.assertNotIn("email", me["buddy"])  # the joiner never gets the buddy's email address
        self.assertEqual([w["week"] for w in me["induction"]["weeks"]], [1, 2, 3, 4])
        self.assertEqual(me["induction"]["current_week"], 2)
        self.assertFalse(me["review"]["open"])

    def test_ticking_and_unticking_an_item(self):
        self.pair()
        url = f"/api/portal/induction/{self.items[0].pk}/"
        self.assertEqual(self.client.post(url, {"done": True}, format="json").data["done"], 1)
        self.assertEqual(self.me().data["induction"]["done"], 1)
        self.assertEqual(self.client.post(url, {"done": False}, format="json").data["done"], 0)

    def test_the_review_opens_after_4_weeks_and_is_sent_once(self):
        pairing = self.pair(joined_days_ago=10)
        self.assertEqual(self.client.post("/api/portal/review/", {"scores": [5, 4, 5]}, format="json").status_code, 400)

        Pairing.objects.filter(pk=pairing.pk).update(start_date=date.today() - timedelta(days=28))
        self.assertTrue(self.me().data["review"]["open"])
        self.assertEqual(self.client.post("/api/portal/review/", {"scores": [5, 4]}, format="json").status_code, 400)
        ok = self.client.post("/api/portal/review/", {"scores": [5, 4, 5], "comment": "Great"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(Feedback.objects.get(pairing=pairing).comment, "Great")
        self.assertTrue(self.me().data["review"]["submitted"])
        again = self.client.post("/api/portal/review/", {"scores": [1, 1, 1]}, format="json")
        self.assertEqual(again.status_code, 400)


class BuddyPortalTests(PortalBase):
    def test_buddy_follows_their_joiners_induction_read_only(self):
        self.pair()
        self.joiner.induction_ticks.create(item=self.items[0])
        self.sign_in("E1", "222222")
        me = self.me().data
        self.assertEqual(me["profile"]["status"], "submitted")
        self.assertEqual([j["name"] for j in me["joiners"]], ["Priya Sharma"])
        self.assertEqual(me["joiners"][0]["induction"]["done"], 1)
        r = self.client.post(f"/api/portal/induction/{self.items[1].pk}/", {"done": True}, format="json")
        self.assertEqual(r.status_code, 403)  # only the joiner ticks
        self.assertEqual(self.client.post("/api/portal/review/", {"scores": [5, 5, 5]}, format="json").status_code, 403)


class DemoSignInTests(PortalBase):
    URL = "/api/auth/demo/"

    def test_lists_joiners_and_buddies_and_signs_one_in_without_a_code(self):
        people = self.client.get(self.URL).data["people"]
        self.assertEqual([(p["kind"], p["username"]) for p in people], [("joiner", "C1"), ("buddy", "E1")])
        self.assertEqual(self.client.post(self.URL, {"username": "E1"}, format="json").data["to"], "/portal")
        self.assertEqual(self.me().data["name"], "Ravi Rao")
        self.assertEqual(self.client.post(self.URL, {"username": "nobody"}, format="json").status_code, 400)

    def test_a_joiner_and_buddy_sharing_a_username_open_the_one_clicked(self):
        self.buddy.employee_id = "C1"  # the same username as the joiner
        self.buddy.save()
        self.client.post(self.URL, {"username": "C1", "kind": "joiner"}, format="json")
        self.assertEqual(self.me().data["kind"], "joiner")
        self.client.post(self.URL, {"username": "C1", "kind": "buddy"}, format="json")
        self.assertEqual(self.me().data["kind"], "buddy")

    def test_the_joiner_sees_the_day_to_answer_by(self):
        self.client.post(self.URL, {"username": "C1", "kind": "joiner"}, format="json")
        self.assertIsNotNone(self.me().data["quiz"]["due"])

    def test_it_is_a_404_when_switched_off(self):
        from django.test import override_settings
        with override_settings(DEMO_SIGN_IN=False):
            self.assertEqual(self.client.get(self.URL).status_code, 404)
            self.assertEqual(self.client.post(self.URL, {"username": "C1"}, format="json").status_code, 404)

    def test_the_real_settings_tie_it_to_debug(self):
        import config.settings as real
        self.assertEqual(real.DEMO_SIGN_IN, real.DEBUG)
