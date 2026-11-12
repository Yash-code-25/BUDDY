"""The daily job as an address for Vercel Cron: only with the secret."""
from django.test import TestCase, override_settings


class DailyCronTests(TestCase):
    URL = "/api/cron/daily/"

    @override_settings(CRON_SECRET="s3cret")
    def test_runs_with_the_secret(self):
        r = self.client.get(self.URL, HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertIn("prejoining_emails", r.json()["done"])

    @override_settings(CRON_SECRET="s3cret")
    def test_refuses_without_or_with_a_wrong_secret(self):
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.client.get(self.URL, HTTP_AUTHORIZATION="Bearer nope").status_code, 403)

    @override_settings(CRON_SECRET="")
    def test_refuses_everyone_when_no_secret_is_set(self):
        self.assertEqual(self.client.get(self.URL, HTTP_AUTHORIZATION="Bearer ").status_code, 403)

    @override_settings(CRON_SECRET="s3cret")
    def test_only_get(self):
        self.assertEqual(self.client.post(self.URL, HTTP_AUTHORIZATION="Bearer s3cret").status_code, 405)
