from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from compass_app.models import Buddy, Settings

BUDDY = {"employee_id": "E100", "name": "Ravi Rao", "email": "ravi@x.com",
         "department": "Sales", "location": "Mumbai"}


class DepartmentAndLocationListTests(APITestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("hr", password="pw", is_staff=True))

    def add_buddy(self, **changes):
        return self.client.post("/api/hr/buddies/", {**BUDDY, **changes}, format="json")

    def test_a_value_from_the_list_is_stored_in_the_lists_spelling(self):
        self.assertEqual(self.add_buddy(department=" sales ", location="MUMBAI").status_code, 201)
        buddy = Buddy.objects.get()
        self.assertEqual((buddy.department, buddy.location), ("Sales", "Mumbai"))

    def test_a_value_not_on_the_list_is_refused(self):
        r = self.add_buddy(department="Saels")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Department must be one of", str(r.json()))
        self.assertFalse(Buddy.objects.exists())

    def test_csv_rows_with_a_wrong_value_are_reported(self):
        csv = ("candidate_id,name,personal_email,department,location,date_of_joining\n"
               "C001,Yash,y@x.com,Sales,Mumbai,2026-12-01\n"
               "C002,Nia,n@x.com,Sales,Mumbay,2026-12-01\n")
        result = self.client.post("/api/hr/joiners/import/", {"csv": csv}, format="json").json()
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["errors"][0]["row"], 3)
        self.assertIn("Location must be one of", result["errors"][0]["error"])

    def test_the_drop_downs_offer_the_lists(self):
        options = self.client.get("/api/hr/filters/").json()
        s = Settings.load()
        self.assertEqual((options["department"], options["location"]), (s.departments, s.locations))

    def test_admin_can_add_to_a_list(self):
        settings = self.client.get("/api/hr/settings/").json()
        settings["departments"] = [*settings["departments"], "Legal", "legal", " "]
        r = self.client.put("/api/hr/settings/", settings, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["departments"][-1], "Legal")
        self.assertEqual(self.add_buddy(department="Legal").status_code, 201)

    def test_a_list_entry_in_use_cannot_be_removed(self):
        self.add_buddy()
        settings = self.client.get("/api/hr/settings/").json()
        settings["departments"] = [d for d in settings["departments"] if d != "Sales"]
        r = self.client.put("/api/hr/settings/", settings, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Sales cannot be removed", str(r.json()))
        self.assertIn("Sales", Settings.load().departments)

    def test_editing_a_buddy_checks_the_lists_too(self):
        self.add_buddy()
        buddy = Buddy.objects.get()
        r = self.client.patch(f"/api/hr/buddies/{buddy.pk}/", {"department": "Finanse"}, format="json")
        self.assertEqual(r.status_code, 400)
        buddy.refresh_from_db()
        self.assertEqual(buddy.department, "Sales")
