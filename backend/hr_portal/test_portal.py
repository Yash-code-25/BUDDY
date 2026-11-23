from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from compass_app.matching import run_match_for_joiner
from compass_app.models import AuditLog, Buddy, InductionItem, Joiner, MatchRun, Pairing, Response, Settings
from compass_app.testing import J, WORKED, make_question_set
from feedback.models import Feedback


User = get_user_model()


class AdminBase(APITestCase):
    def setUp(self):
        self.qs = make_question_set()
        # No passwords: the tests sign in with force_login, and hashing is slow.
        self.admin = User.objects.create_user("pa", is_staff=True)
        self.mumbai = self.add_joiner("C001", "Yash Chavan", "Mumbai")
        self.pune = self.add_joiner("C002", "Pooja Rao", "Pune")
        self.buddies = {k: self.add_buddy(k, v) for k, v in WORKED.items()}
        run_match_for_joiner(self.mumbai)
        self.client.force_login(self.admin)

    def add_joiner(self, cid, name, location, answers=J):
        joiner = Joiner.objects.create(
            name=name, candidate_id=cid, personal_email=f"{cid}@x.com", department="Sales",
            location=location, date_of_joining=date.today() + timedelta(days=10),
        )
        Response.submitted(joiner, self.qs, answers).save()
        return joiner

    def add_buddy(self, key, a, status=Buddy.PoolStatus.ACTIVE, location="Mumbai", done=True):
        buddy = Buddy.objects.create(
            employee_id=key, name=f"Buddy {key}", email=f"{key}@x.com", department="Sales",
            location=location, pool_status=status,
        )
        if done:
            Response.submitted(buddy, self.qs, a).save()
        return buddy

    def pair(self, joiner, key, status=Pairing.Status.ACTIVE):
        start, end = Pairing.dates_for(joiner)
        return Pairing.objects.create(joiner=joiner, buddy=self.buddies[key], source=Pairing.Source.SYSTEM,
                                      status=status, start_date=start, end_date=end)


class AccessTests(AdminBase):
    def test_only_program_admins_use_the_admin_screens(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/hr/joiners/").status_code, 403)
        self.client.force_login(User.objects.create_user("someone"))  # not staff
        self.assertEqual(self.client.get("/api/hr/joiners/").status_code, 403)

    def test_a_program_admin_and_the_superuser_open_everything(self):
        for user in (self.admin, User.objects.create_superuser("dev", "", "x")):
            self.client.force_login(user)
            for url in ("/api/hr/home/", "/api/hr/settings/", "/api/hr/audit/", "/api/hr/induction/", "/api/hr/reports/summary/"):
                self.assertEqual(self.client.get(url).status_code, 200, (user, url))

    def test_there_are_no_demo_sign_ins(self):
        self.assertEqual(self.client.get("/api/hr/auth/quick/").status_code, 404)


class JoinerTests(AdminBase):
    NEW = {
        "candidate_id": "C100", "name": "New Person", "personal_email": "new@x.com",
        "department": "Finance", "location": "Mumbai", "date_of_joining": "2026-12-01",
    }

    def test_queue_filters(self):
        get = lambda q: [r["name"] for r in self.client.get(f"/api/hr/joiners/?{q}").data]
        self.assertEqual(get("location=Pune"), ["Pooja Rao"])
        self.assertEqual(get("band=Strong"), ["Yash Chavan"])
        self.assertEqual(get("tier=1"), ["Yash Chavan"])
        self.assertEqual(get("q=pooja"), ["Pooja Rao"])
        self.assertEqual(get("status=PAIRED"), [])
        self.assertEqual(self.client.get("/api/hr/joiners/?doj_from=abc").status_code, 400)

    def test_export_has_the_filtered_joiners(self):
        r = self.client.get("/api/hr/joiners/?location=Pune&export=csv")
        lines = r.content.decode("utf-8-sig").strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Pooja Rao", lines[1])
        self.assertIn("spreadsheetml", self.client.get("/api/hr/joiners/?export=xlsx")["Content-Type"])

    def test_a_deleted_joiner_shows_only_under_the_deleted_filter(self):
        b = self.buddies["B"]
        past = self.pair(self.mumbai, "B")
        Buddy.objects.filter(pk=b.pk).update(active_joiners=1, total_joiners_buddied=1)
        url = f"/api/hr/joiners/{self.mumbai.pk}/"
        mail.outbox.clear()

        self.assertEqual(self.client.delete(url).status_code, 204)
        names = lambda q="": [r["name"] for r in self.client.get(f"/api/hr/joiners/?{q}").data]
        self.assertEqual(names(), ["Pooja Rao"])
        self.assertEqual(names("status=DELETED"), ["Yash Chavan"])
        detail = self.client.get(url).data  # still opens, read-only
        self.assertTrue(detail["deleted"])
        self.assertEqual(self.client.post(f"{url}action/", {"action": "hold"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)

        # the buddy is freed and told, and the pairing is gone from their history
        b.refresh_from_db()
        self.assertEqual((b.active_joiners, b.total_joiners_buddied), (0, 0))
        self.assertEqual(Pairing.all_objects.get(pk=past.pk).status, Pairing.Status.CANCELLED)
        self.assertEqual(self.client.get(f"/api/hr/buddies/{b.pk}/").data["history"], [])
        self.assertIn("taken out of COMPASS", mail.outbox[0].body)
        self.assertEqual(self.client.get("/api/hr/reports/summary/").data["total_joiners"], 1)

        # cannot be added again, by form or CSV
        again = {"candidate_id": "C001", "name": "Yash", "personal_email": "y@x.com", "department": "Sales",
                 "location": "Mumbai", "date_of_joining": "2026-12-01"}
        r = self.client.post("/api/hr/joiners/", again, format="json")
        self.assertIn("was deleted", str(r.data))
        text = "candidate_id,name,personal_email,department,location,date_of_joining\nC001,Y,y@x.com,Sales,Mumbai,2026-12-01\n"
        self.assertEqual(len(self.client.post("/api/hr/joiners/import/", {"csv": text}, format="json").data["errors"]), 1)

    def test_add_joiner_and_reject_bad_input(self):
        self.assertEqual(self.client.post("/api/hr/joiners/", self.NEW, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/hr/joiners/", self.NEW, format="json").status_code, 400)
        for bad in ({"candidate_id": "C101", "personal_email": "nope"},
                    {"candidate_id": "C102", "date_of_joining": "01/12/2026"}):
            self.assertEqual(self.client.post("/api/hr/joiners/", {**self.NEW, **bad}, format="json").status_code, 400)

    def test_csv_import_creates_updates_reports_errors_and_sends_logins(self):
        header = "candidate_id,name,personal_email,department,location,date_of_joining\n"
        text = (header + "C200,Asha K,asha@x.com,Sales,Mumbai,2026-12-01\n"
                "C201,Ben L,ben@x.com,Finance,Pune,2026-12-05\n"
                "C202,Bad Row,not-an-email,Sales,Mumbai,2026-12-05\n")
        result = self.client.post("/api/hr/joiners/import/", {"csv": text}, format="json").data
        self.assertEqual((result["created"], result["updated"], len(result["errors"])), (2, 0, 1))
        self.assertEqual(result["errors"][0]["row"], 4)
        self.assertEqual(sum(m.subject == "Your COMPASS login details" for m in mail.outbox), 2)
        again = self.client.post("/api/hr/joiners/import/", {"csv": text}, format="json").data
        self.assertEqual((again["created"], again["updated"]), (0, 2))

    def test_joining_date_is_fixed_once_a_buddy_is_assigned(self):
        self.pair(self.mumbai, "B")
        later = (self.mumbai.date_of_joining + timedelta(days=7)).isoformat()
        csv = f"candidate_id,name,personal_email,department,location,date_of_joining\nC001,Yash,C001@x.com,Sales,Mumbai,{later}\n"
        r = self.client.post("/api/hr/joiners/import/", {"csv": csv}, format="json").data
        self.assertEqual((r["updated"], len(r["errors"])), (0, 1))

    def test_actions_hold_release_manual_note_not_required(self):
        act = lambda **body: self.client.post(f"/api/hr/joiners/{self.mumbai.pk}/action/", body, format="json")
        self.assertEqual(act(action="hold").data["status"], "ON_HOLD")
        self.assertEqual(act(action="release").data["status"], "AWAITING_PAIRING")
        self.assertEqual(act(action="manual").data["status"], "MANUAL")
        self.assertEqual(act(action="note").status_code, 400)
        self.assertEqual(act(action="note", note="Called the manager").status_code, 200)
        self.assertEqual(act(action="nonsense").status_code, 400)
        self.assertEqual(act(action="not_required", note="Rehire").data["status"], "CLOSED")
        self.mumbai.refresh_from_db()
        self.assertIn("Called the manager", self.mumbai.notes)
        notes = self.client.get(f"/api/hr/joiners/{self.mumbai.pk}/").data["joiner"]["notes"]
        self.assertEqual([n["text"] for n in notes], ["Buddy not required. Rehire", "Called the manager"])
        self.assertNotIn(self.admin.username, self.mumbai.notes)  # written as "Admin"
        self.assertRegex(notes[0]["time"], r"^\d{2}:\d{2}$")

    def test_older_notes_and_notes_over_several_lines_are_read_too(self):
        from .views import note_entries
        self.assertEqual(note_entries("[2026-11-03 superuser] First\n[2026-11-05 14:30 Admin] Line one\nline two"), [
            {"date": "2026-11-05", "time": "14:30", "text": "Line one\nline two"},
            {"date": "2026-11-03", "time": "", "text": "First"},
        ])

    def test_reminder_only_for_joiners_who_have_not_answered_and_it_reopens_the_week(self):
        url = f"/api/hr/joiners/{self.mumbai.pk}/action/"
        self.assertEqual(self.client.post(url, {"action": "remind"}, format="json").status_code, 400)
        waiting = Joiner.objects.create(
            name="Late Lata", candidate_id="C300", personal_email="lata@x.com", department="Sales",
            location="Mumbai", date_of_joining=date.today() + timedelta(days=5),
            quiz_link_sent_on=date.today() - timedelta(days=9),
        )
        r = self.client.post(f"/api/hr/joiners/{waiting.pk}/action/", {"action": "remind"}, format="json")
        self.assertEqual(r.status_code, 200)
        waiting.refresh_from_db()
        self.assertEqual(waiting.quiz_link_sent_on, date.today())

    def test_detail_shows_the_buddy_and_the_induction_progress(self):
        item = InductionItem.objects.create(week=1, day="Day 1", activity="Welcome")
        self.pair(self.mumbai, "B")
        self.mumbai.induction_ticks.create(item=item)
        data = self.client.get(f"/api/hr/joiners/{self.mumbai.pk}/").data
        self.assertEqual(data["pairing"]["buddy_name"], "Buddy B")
        self.assertTrue(data["pairing"]["can_change"])
        self.assertEqual((data["induction"]["done"], data["induction"]["total"]), (1, 1))

    def test_assigning_refuses_a_buddy_paused_after_the_run(self):
        top = MatchRun.objects.get(joiner=self.mumbai).results["shown"][0]
        Buddy.objects.filter(employee_id=top["buddy_id"]).update(pool_status=Buddy.PoolStatus.PAUSED)
        r = self.client.post(f"/api/hr/joiners/{self.mumbai.pk}/assign/", {"buddy_id": top["buddy_id"]}, format="json")
        self.assertEqual(r.status_code, 400)


class BuddyGroupsTests(AdminBase):
    URL = "/api/hr/buddies/groups/"

    def test_buddies_are_grouped_by_department_and_location(self):
        self.add_buddy("P1", J, location="Pune")
        groups = self.client.get(self.URL).data
        self.assertEqual([(g["department"], g["location"]) for g in groups], [("Sales", "Mumbai"), ("Sales", "Pune")])
        self.assertEqual(len(groups[0]["buddies"]), 6)

    def test_each_buddy_lists_only_the_joiners_they_look_after_now(self):
        self.pair(self.mumbai, "B")
        self.pair(self.pune, "B", status=Pairing.Status.CLOSED)
        bharat = next(b for b in self.client.get(self.URL).data[0]["buddies"] if b["employee_id"] == "B")
        self.assertEqual([j["name"] for j in bharat["joiners"]], ["Yash Chavan"])

    def test_filters_apply_to_the_groups_too(self):
        found = self.client.get(self.URL + "?q=buddy b").data
        self.assertEqual([b["employee_id"] for g in found for b in g["buddies"]], ["B"])


class BuddyPoolTests(AdminBase):
    def test_add_buddy(self):
        payload = {"employee_id": "E900", "name": "Nina Shah", "email": "nina@x.com",
                   "department": "Sales", "location": "Mumbai"}
        self.assertEqual(self.client.post("/api/hr/buddies/", payload, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/hr/buddies/", payload, format="json").status_code, 400)

    def test_csv_import_with_historic_count(self):
        text = ("employee_id,name,email,department,location,total_joiners_buddied\n"
                "E901,Ola P,ola@x.com,Sales,Mumbai,7\nE902,Bad,bad,Sales,Mumbai,1\n")
        result = self.client.post("/api/hr/buddies/import/", {"csv": text}, format="json").data
        self.assertEqual((result["created"], len(result["errors"])), (1, 1))
        self.assertEqual(Buddy.objects.get(employee_id="E901").total_joiners_buddied, 7)

    def test_filters_status_cmpbd_and_answer(self):
        self.add_buddy("N1", J, status=Buddy.PoolStatus.PAUSED, done=False)
        get = lambda q: sorted(r["employee_id"] for r in self.client.get(f"/api/hr/buddies/?{q}").data)
        self.assertEqual(get("cmpbd=not_started"), ["N1"])
        self.assertEqual(get("status=PAUSED"), ["N1"])
        self.assertEqual(get("q4=5"), ["B"])
        self.assertEqual(get("q4=1,2"), ["A", "C", "D"])
        self.pair(self.mumbai, "B")
        self.pair(self.pune, "C", status=Pairing.Status.CLOSED)  # finished: not assigned now
        self.assertEqual(get("status=ASSIGNED"), ["B"])
        self.assertEqual(get("status=ASSIGNED&location=Pune"), [])

    def test_actions(self):
        act = lambda b, a: self.client.post(f"/api/hr/buddies/{b.pk}/action/", {"action": a}, format="json")
        b = self.buddies["B"]
        self.assertEqual(act(b, "pause").data["pool_status"], "PAUSED")
        self.assertEqual(act(b, "resume").data["pool_status"], "ACTIVE")
        fresh = self.add_buddy("N2", J, status=Buddy.PoolStatus.PAUSED, done=False)
        self.assertEqual(act(fresh, "resume").status_code, 400)
        self.assertEqual(act(fresh, "remind").status_code, 200)
        self.assertEqual(act(b, "remove").data["pool_status"], "REMOVED")

    def test_export_has_the_filtered_buddies_with_answers_and_current_joiners(self):
        self.pair(self.mumbai, "B")
        r = self.client.get("/api/hr/buddies/?q=Buddy B&export=csv")
        self.assertEqual(r.status_code, 200)
        lines = r.content.decode("utf-8-sig").strip().splitlines()
        self.assertEqual(len(lines), 2)  # header and Buddy B only: the filter applies
        self.assertIn("Looking after now", lines[0])
        self.assertIn("Yash Chavan", lines[1])
        self.assertIn("spreadsheetml", self.client.get("/api/hr/buddies/?export=xlsx")["Content-Type"])

    def test_retake_reopens_the_profile_and_reset_clears_it(self):
        b = self.buddies["B"]
        url = f"/api/hr/buddies/{b.pk}/action/"
        self.assertEqual(self.client.post(url, {"action": "retake"}, format="json").status_code, 200)
        self.assertIsNone(Response.objects.get(buddy=b).submitted_at)
        self.assertEqual(self.client.post(url, {"action": "reset"}, format="json").status_code, 200)
        self.assertFalse(Response.objects.filter(buddy=b).exists())

    def test_detail_shows_answers_and_every_joiner_they_have_had(self):
        self.pair(self.mumbai, "B")
        self.pair(self.pune, "B", status=Pairing.Status.CLOSED)
        b = self.buddies["B"]
        data = self.client.get(f"/api/hr/buddies/{b.pk}/").data
        self.assertEqual(len(data["answers"]), 5)
        self.assertEqual(sorted((h["joiner"], h["status"]) for h in data["history"]),
                         [("Pooja Rao", "CLOSED"), ("Yash Chavan", "ACTIVE")])
        r = self.client.patch(f"/api/hr/buddies/{b.pk}/", {"location": "Delhi", "intro": "Hi!"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.patch(f"/api/hr/buddies/{b.pk}/", {"email": "nope"}, format="json").status_code, 400)

    def test_buddy_list_query_count_does_not_grow_with_the_pool(self):
        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get("/api/hr/buddies/?version=1")
            return len(ctx.captured_queries)

        before = count()
        for n in range(5):
            self.add_buddy(f"X{n}", J)
        self.assertEqual(count(), before)


class InductionAdminTests(AdminBase):
    URL = "/api/hr/induction/"

    def test_common_day_1_rows_add_edit_and_remove(self):
        a = self.client.post(self.URL, {"week": 3, "day": "Workstation", "activity": "Laptop", "owner": "IT"}, format="json").data
        b = self.client.post(self.URL, {"day": "Tools", "activity": "Teams"}, format="json").data
        self.assertEqual([(i["activity"], i["week"]) for i in self.client.get(self.URL).data],
                         [("Laptop", 1), ("Teams", 1)])  # the common rows are all Day 1
        self.client.patch(f"{self.URL}{a['id']}/", {"week": 2, "activity": "Laptop and bag"}, format="json")
        self.assertEqual(self.client.get(self.URL).data[0]["activity"], "Laptop and bag")
        self.assertEqual(self.client.get(self.URL).data[0]["week"], 1)
        self.assertEqual(self.client.delete(f"{self.URL}{b['id']}/").status_code, 204)
        self.assertEqual(len(self.client.get(self.URL).data), 1)
        self.assertTrue(AuditLog.objects.filter(action="induction_item_removed").exists())

    def test_each_joiner_has_their_own_plan_after_day_1(self):
        other = self.pune
        self.client.post(self.URL, {"day": "Workstation", "activity": "Laptop"}, format="json")
        url = f"{self.URL}joiners/{self.mumbai.pk}/"
        self.assertEqual(self.client.post(url, {"week": 2, "day": "Day 6", "activity": "Shadow"}, format="json").status_code, 201)
        self.client.post(url, {"week": 1, "day": "Day 2", "activity": "Meet the team"}, format="json")
        plan = self.client.get(url).data["induction"]
        self.assertEqual([(i["activity"], i["common"]) for i in plan["weeks"][0]["items"]],
                         [("Laptop", True), ("Meet the team", False)])
        self.assertEqual([i["activity"] for i in plan["weeks"][1]["items"]], ["Shadow"])
        theirs = self.client.get(f"{self.URL}joiners/{other.pk}/").data["induction"]
        self.assertEqual(theirs["total"], 1)  # only the common Day 1

        laptop = InductionItem.objects.get(activity="Laptop")
        self.mumbai.induction_ticks.create(item=laptop)
        rows = {r["name"]: r for r in self.client.get(f"{self.URL}joiners/").data}
        self.assertEqual((rows["Yash Chavan"]["done"], rows["Yash Chavan"]["total"], rows["Yash Chavan"]["percent"]), (1, 3, 33))
        self.assertEqual((rows["Pooja Rao"]["percent"], rows["Pooja Rao"]["own_items"]), (0, 0))
        self.assertEqual(self.client.get(self.URL).data[0]["activity"], "Laptop")  # own rows stay off the common list

    def test_day_1_can_be_changed_for_one_joiner_alone(self):
        welcome = self.client.post(self.URL, {"day": "Day 1", "activity": "Welcome", "owner": "HR"}, format="json").data
        laptop = self.client.post(self.URL, {"day": "Day 1", "activity": "Laptop", "owner": "IT"}, format="json").data
        self.mumbai.induction_ticks.create(item_id=welcome["id"])  # ticked before the change
        plan_url = f"{self.URL}joiners/{self.mumbai.pk}/"
        day_one = lambda j: [(i["activity"], i["owner"]) for i in
                             self.client.get(f"{self.URL}joiners/{j.pk}/").data["induction"]["weeks"][0]["items"]]

        # edit a common row on Yash's page: only Yash's Day 1 changes
        r = self.client.patch(f"{self.URL}{laptop['id']}/?joiner={self.mumbai.pk}",
                              {"activity": "Laptop and badge", "week": 3}, format="json")
        self.assertEqual((r.status_code, r.data["week"]), (200, 1))  # a Day 1 row stays in week 1
        self.assertEqual(day_one(self.mumbai), [("Welcome", "HR"), ("Laptop and badge", "IT")])
        self.assertEqual(day_one(self.pune), [("Welcome", "HR"), ("Laptop", "IT")])  # everyone else
        self.assertEqual([i["activity"] for i in self.client.get(self.URL).data], ["Welcome", "Laptop"])
        plan = self.client.get(plan_url).data["induction"]
        self.assertTrue(plan["own_day_one"])
        self.assertEqual((plan["done"], plan["weeks"][0]["items"][0]["done"]), (1, True))  # the tick moved

        # remove one and add one, still for Yash alone; "Day 1" in week 1 joins their Day 1
        mine = plan["weeks"][0]["items"]
        self.client.post(plan_url, {"week": 1, "day": "Day 2", "activity": "Team lunch"}, format="json")
        self.client.post(plan_url, {"week": 1, "day": "Day 1", "activity": "Meet the CEO"}, format="json")
        self.assertEqual(self.client.delete(f"{self.URL}{mine[1]['id']}/").status_code, 204)
        self.assertEqual([a for a, _ in day_one(self.mumbai)], ["Welcome", "Meet the CEO", "Team lunch"])
        self.assertEqual(len(day_one(self.pune)), 2)

        # a common row edited for everyone no longer reaches Yash, and the joiner portal check agrees
        self.client.patch(f"{self.URL}{welcome['id']}/", {"activity": "Big welcome"}, format="json")
        self.assertEqual(day_one(self.pune)[0][0], "Big welcome")
        self.assertEqual(day_one(self.mumbai)[0][0], "Welcome")
        from compass_app.induction import belongs_to
        self.mumbai.refresh_from_db()
        self.assertFalse(belongs_to(InductionItem.objects.get(pk=welcome["id"]), self.mumbai))
        rows = {r["name"]: r for r in self.client.get(f"{self.URL}joiners/").data}
        self.assertEqual((rows["Yash Chavan"]["done"], rows["Yash Chavan"]["total"]), (1, 3))

        # back to the common Day 1: the copies go, the tick returns to the common row
        self.assertEqual(self.client.delete(f"{plan_url}day-one/").status_code, 204)
        plan = self.client.get(plan_url).data["induction"]
        self.assertFalse(plan["own_day_one"])
        self.assertEqual([i["activity"] for i in plan["weeks"][0]["items"]], ["Big welcome", "Laptop", "Team lunch"])
        self.assertEqual(plan["done"], 1)
        self.assertTrue(AuditLog.objects.filter(action="induction_day_one_reset").exists())

    def test_rows_are_checked(self):
        for bad in ({"week": 5, "day": "Day 1", "activity": "x"}, {"week": 1, "day": "", "activity": "x"},
                    {"week": 1, "day": "Day 1", "activity": " "}):
            self.assertEqual(self.client.post(f"{self.URL}joiners/{self.mumbai.pk}/", bad, format="json").status_code, 400, bad)
        self.assertEqual(self.client.post(self.URL, {"day": "", "activity": "x"}, format="json").status_code, 400)


class SettingsAndAuditTests(AdminBase):
    def test_settings_update_validates_and_is_audited(self):
        data = self.client.get("/api/hr/settings/").data
        self.assertNotIn("acceptance_working_days", data)
        data.update(good_threshold=3, weaker_threshold=2, manual_cutoff_day=1)
        self.assertEqual(self.client.put("/api/hr/settings/", data, format="json").status_code, 200)
        s = Settings.load()
        self.assertEqual((s.good_threshold, s.manual_cutoff_day), (3, 1))
        self.assertEqual(AuditLog.objects.get(action="settings_changed").before["good_threshold"], 4)

    def test_settings_reject_bad_values(self):
        base = self.client.get("/api/hr/settings/").data
        for change in ({"strong_threshold": 2}, {"amber_gap": 3, "red_gap": 3}, {"close_gap": 9},
                       {"joiner_intro": "  "}):
            self.assertEqual(self.client.put("/api/hr/settings/", {**base, **change}, format="json").status_code, 400, change)

    def test_audit_log_filters(self):
        self.client.post(f"/api/hr/joiners/{self.mumbai.pk}/action/", {"action": "hold"}, format="json")
        rows = self.client.get("/api/hr/audit/?action=joiner_hold&user=pa").data
        self.assertEqual([r["user"] for r in rows], ["pa"])
        self.assertEqual(self.client.get("/api/hr/audit/?date_from=oops").status_code, 400)


class HomeAndReportTests(AdminBase):
    def test_home_tiles_count_by_status(self):
        Joiner.objects.filter(pk=self.pune.pk).update(compass_status=Joiner.Status.AWAITING_PAIRING)
        tiles = {t["key"]: t for t in self.client.get("/api/hr/home/").data["tiles"]}
        self.assertEqual(tiles["awaiting_pairing"]["count"], 2)
        self.assertEqual(tiles["pool"]["count"], 6)
        self.assertNotIn("awaiting_buddy", tiles)

    def test_the_two_tables_load_export_and_name_the_buddy(self):
        pairing = self.pair(self.mumbai, "B")
        Feedback.objects.create(pairing=pairing, q1=5, q2=4, q3=5, comment="Kind")
        for name in ("buddies", "reviews"):
            data = self.client.get(f"/api/hr/reports/{name}/").data
            self.assertEqual(len(data["buddy_ids"]), len(data["rows"]), name)
            self.assertEqual(len(data["attention"]), len(data["rows"]), name)
            for kind in ("csv", "xlsx"):
                self.assertEqual(self.client.get(f"/api/hr/reports/{name}/?export={kind}").status_code, 200)
        self.assertEqual(self.client.get("/api/hr/reports/joiners/").status_code, 404)  # joiners have their own page

        reviews = self.client.get("/api/hr/reports/reviews/").data
        self.assertEqual((reviews["rows"][0][1], reviews["buddy_ids"]), ("Buddy B", [self.buddies["B"].pk]))
        self.assertEqual(reviews["columns"], ["Joiner", "Buddy", "Date", "Q1", "Q2", "Q3", "Total", "Details"])
        self.assertEqual(reviews["rows"][0][3:7], [5, 4, 5, "14 / 15"])
        export = self.client.get("/api/hr/reports/reviews/?export=csv").content.decode("utf-8-sig").splitlines()
        self.assertIn("Made me feel welcomed", export[0])
        self.assertIn("5,4,5,14 / 15,Kind", export[1])  # each score as a number in the download
        detail = reviews["details"][0]
        self.assertEqual([(q["question"], q["score"], q["label"]) for q in detail["questions"]], [
            ("Made me feel welcomed", 5, "Very much"),
            ("Introduced me to the right people", 4, "Mostly"),
            ("Answered questions, or found who could answer them for me", 5, "Very much"),
        ])
        self.assertEqual((detail["comment"], detail["total"], detail["max"]), ("Kind", 14, 15))
        self.assertNotIn("details", buddies_data := self.client.get("/api/hr/reports/buddies/").data)
        self.assertTrue(buddies_data["rows"])
        buddies = self.client.get("/api/hr/reports/buddies/").data
        bharat = buddies["rows"][[r[0] for r in buddies["rows"]].index("Buddy B")]
        self.assertEqual(bharat[-1], 4.7)

    def test_review_questions_are_worded_in_settings_and_old_reviews_keep_theirs(self):
        pairing = self.pair(self.mumbai, "B")
        old = ["Made me feel welcomed", "Introduced me to the right people",
               "Answered questions, or found who could answer them for me"]
        Feedback.objects.create(pairing=pairing, q1=5, q2=4, q3=3, questions=old)
        data = self.client.get("/api/hr/settings/").data
        self.assertEqual(data["review_questions"], old)

        for bad in (["One", "Two"], ["One", "  ", "Three"], ["x" * 201, "Two", "Three"]):
            r = self.client.put("/api/hr/settings/", {**data, "review_questions": bad}, format="json")
            self.assertEqual(r.status_code, 400, bad)
        new = ["Was friendly", "Showed me around", "Helped with my questions"]
        r = self.client.put("/api/hr/settings/", {**data, "review_questions": [" Was  friendly ", *new[1:]]}, format="json")
        self.assertEqual(r.data["review_questions"], new)  # spaces tidied
        self.assertTrue(AuditLog.objects.filter(action="settings_changed", after__has_key="review_questions").exists())

        reviews = self.client.get("/api/hr/reports/reviews/").data
        export = self.client.get("/api/hr/reports/reviews/?export=csv").content.decode("utf-8-sig").splitlines()
        self.assertTrue(export[0].startswith("Joiner,Buddy,Date,Was friendly,"))  # the download uses today's wording
        self.assertEqual([q["question"] for q in reviews["details"][0]["questions"]], old)  # the review keeps its own

    def test_buddies_without_a_profile_are_marked_for_attention(self):
        self.add_buddy("N1", J, status=Buddy.PoolStatus.PAUSED, done=False)
        data = self.client.get("/api/hr/reports/buddies/").data
        marked = {r[0]: a for r, a in zip(data["rows"], data["attention"])}
        self.assertTrue(marked["Buddy N1"])
        self.assertFalse(marked["Buddy B"])

    def test_the_summary_numbers(self):
        data = self.client.get("/api/hr/reports/summary/").data
        self.assertEqual((data["total_assigned"], data["in_induction"], data["average_review"]), (0, 0, None))
        self.assertEqual(data["total_joiners"], Joiner.objects.count())
        self.assertEqual(data["total_buddies"], Buddy.objects.exclude(pool_status=Buddy.PoolStatus.REMOVED).count())
