import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

INDEX = b'<!doctype html><html><body><div id="root"></div><script src="/assets/app.js"></script></body></html>'


def body(response) -> bytes:
    return b"".join(response.streaming_content) if response.streaming else response.content


class FrontendServingTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.dist = root / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "index.html").write_bytes(INDEX)
        (self.dist / "assets" / "app.js").write_bytes(b"console.log('compass')")
        (self.dist / "favicon.svg").write_bytes(b"<svg></svg>")
        (root / "secret.txt").write_bytes(b"TOP SECRET")
        override = override_settings(FRONTEND_DIST=self.dist)
        override.enable()
        self.addCleanup(override.disable)

    def get(self, address):
        """A GET that closes the file behind the response, so Windows lets the temp folder go."""
        response = self.client.get(address)
        self.addCleanup(response.close)
        return response

    def test_every_page_address_gets_the_react_app(self):
        for address in ("/", "/login", "/portal", "/hr/joiners/5", "/assess/joiner/abc"):
            response = self.get(address)
            self.assertEqual(response.status_code, 200, address)
            self.assertEqual(body(response), INDEX, address)
            self.assertIn("text/html", response["Content-Type"])

    def test_the_page_is_never_cached_so_a_rebuild_is_picked_up(self):
        self.assertEqual(self.get("/hr").get("Cache-Control"), "no-cache")

    def test_built_files_are_served_as_they_are(self):
        js = self.get("/assets/app.js")
        self.assertEqual(body(js), b"console.log('compass')")
        self.assertIn("javascript", js["Content-Type"])
        self.assertEqual(body(self.get("/favicon.svg")), b"<svg></svg>")

    def test_a_missing_asset_still_gets_the_app_not_a_crash(self):
        self.assertEqual(self.get("/assets/gone.js").status_code, 200)

    def test_unknown_api_addresses_are_real_404s_not_the_web_page(self):
        for address in ("/api/nope/", "/api/hr/nope/", "/api/portal/nope/", "/static/nothing.css"):
            response = self.client.get(address)
            self.assertEqual(response.status_code, 404, address)
            self.assertNotIn(b'id="root"', response.content, address)

    def test_the_real_api_and_django_admin_still_work(self):
        me = self.client.get("/api/hr/auth/me/")
        self.assertEqual(me.status_code, 403)  # the API answers, as JSON, and needs a sign-in
        self.assertEqual(me["Content-Type"], "application/json")
        admin = self.client.get("/admin/")
        self.assertEqual(admin.status_code, 302)
        self.assertIn("/admin/login/", admin["Location"])

    def test_files_outside_the_build_folder_are_never_served(self):
        for address in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
            response = self.get(address)
            self.assertNotIn(b"TOP SECRET", body(response) if response.status_code == 200 else b"", address)

    def test_only_reading_is_allowed(self):
        self.assertEqual(self.client.post("/login").status_code, 405)

    def test_a_clear_message_when_the_app_has_not_been_built(self):
        with override_settings(FRONTEND_DIST=Path(self.tmp.name) / "nothing-here"):
            response = self.client.get("/login")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"npm run build", response.content)


class FrontendSettingsTests(SimpleTestCase):
    def test_the_build_folder_is_frontend_dist_next_to_the_backend(self):
        import config.settings as real

        self.assertEqual((real.FRONTEND_DIST.parent.name, real.FRONTEND_DIST.name), ("frontend", "dist"))

    def test_email_links_point_at_the_one_server(self):
        import config.settings as real

        self.assertEqual(real.FRONTEND_URL, "http://localhost:8000")


class ApiCacheTests(TestCase):
    def test_api_answers_are_never_cached(self):
        r = self.client.get("/api/assessment/joiner/11111111-1111-1111-1111-111111111111/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("no-store", r["Cache-Control"])
