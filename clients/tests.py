import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from candidates.models import Candidate

from .advisor import suggest_tweaks
from .matching import score
from .models import Client, Vacancy


class AdvisorTests(TestCase):
    # TODO(Ivan): extend (combined options, Claude ranking with a mocked client)
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))
        company = Client.objects.create(name="ACME")
        self.vacancy = Vacancy.objects.create(client=company, title="Data Engineer", max_rate_per_hour=80)
        # €6000 -> advised €79.23 without travel; with 50 km by car it goes over €80
        self.candidate = Candidate.objects.create(
            first_name="A", last_name="B", expected_salary_month=6000,
            travel_distance_km=50, transport_type="car", vacancy=self.vacancy,
        )

    @mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_solver_brings_candidate_within_budget(self):
        self.assertEqual(self.candidate.pricing.budget_status, "over")
        options = suggest_tweaks(self.candidate)
        self.assertTrue(options)
        for option in options:
            self.assertLessEqual(Decimal(option["new_rate"]), Decimal(80))

    @mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_apply_tweak(self):
        option = next(o for o in suggest_tweaks(self.candidate) if o["key"] == "salary")
        response = self.client.post(reverse("clients:apply_tweak", args=[self.candidate.pk]),
                                    {"changes": json.dumps(option["changes"])})
        self.assertTrue(response.json()["ok"])
        self.candidate.refresh_from_db()
        self.assertNotEqual(self.candidate.pricing.budget_status, "over")

    @mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_client_pays_travel_option_updates_vacancy(self):
        option = next(o for o in suggest_tweaks(self.candidate) if o["key"] == "client_travel")
        self.client.post(reverse("clients:apply_tweak", args=[self.candidate.pk]), {"changes": option["changes_json"]})
        self.vacancy.refresh_from_db()
        self.assertTrue(self.vacancy.client_pays_travel)

    def test_apply_tweak_rejects_unknown_fields(self):
        response = self.client.post(reverse("clients:apply_tweak", args=[self.candidate.pk]),
                                    {"changes": json.dumps({"first_name": "x"})})
        self.assertEqual(response.status_code, 400)

    def test_match_score_range(self):
        result = score(self.candidate, self.vacancy)
        self.assertTrue(0 <= result["total"] <= 100)
