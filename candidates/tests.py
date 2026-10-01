from decimal import Decimal

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clients.models import Client, Vacancy

from .models import Candidate

VALID = {
    "first_name": "Sanne", "last_name": "de Vries", "status": "intake", "expected_salary_month": "6000",
    "hours_per_week": "40", "transport_type": "car", "remote_days_per_week": "0", "cost_factor": "2.0",
    "margin_per_hour": "10",
}


class CandidateCrudTests(TestCase):
    # TODO(Vidic): extend (filters, validation, over-budget badge)
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))

    def test_list_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("candidates:list")).status_code, 302)

    def test_create_returns_json(self):
        response = self.client.post(reverse("candidates:create"), VALID)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(Candidate.objects.get().pricing.advised_rate, Decimal("79.23"))

    def test_invalid_form_returns_html(self):
        response = self.client.post(reverse("candidates:create"), {**VALID, "first_name": ""})
        self.assertFalse(response.json()["ok"])
        self.assertIn("modal-form", response.json()["html"])

    def test_update_and_delete(self):
        candidate = Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=5000)
        self.client.post(reverse("candidates:update", args=[candidate.pk]), {**VALID, "first_name": "Bram"})
        candidate.refresh_from_db()
        self.assertEqual(candidate.first_name, "Bram")
        response = self.client.post(reverse("candidates:delete", args=[candidate.pk]))
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Candidate.objects.exists())

    def test_margin_must_be_between_5_and_15(self):
        response = self.client.post(reverse("candidates:create"), {**VALID, "margin_per_hour": "20"})
        self.assertFalse(response.json()["ok"])

    @mock.patch("candidates.models.route_distance_km", return_value={"km": Decimal("45.9"), "source": "route"})
    def test_travel_distance_calculated_automatically(self, route):
        company = Client.objects.create(name="ACME", city="Amsterdam")
        vacancy = Vacancy.objects.create(client=company, title="Engineer", city="Amsterdam", max_rate_per_hour=100)
        self.client.post(reverse("candidates:create"), {**VALID, "city": "Utrecht", "vacancy": vacancy.pk})
        self.assertEqual(Candidate.objects.get().travel_distance_km, Decimal("45.9"))
        route.assert_called_once_with("Utrecht", "Amsterdam")

    def test_data_endpoint(self):
        Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=6000)
        data = self.client.get(reverse("candidates:data")).json()["data"]
        self.assertEqual(data[0]["rate"], "79.23")
