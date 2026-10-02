import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from . import travel
from .engine import PricingInput, calculate, rate_to_salary


class SalaryToTariffTests(SimpleTestCase):
    def test_example_from_brief(self):
        # €6000, 40h, factor 2.0, €2.13 travel, €10 margin -> €81.36
        result = calculate(PricingInput(
            salary_month=6000, hours_per_week=40, cost_factor=2.0, margin=10,
            travel_per_hour_override=Decimal("2.13"), max_rate=120,
        ))
        self.assertEqual(result.hourly_wage, Decimal("34.62"))
        self.assertEqual(result.cost_price, Decimal("69.23"))
        self.assertEqual(result.travel_in_tariff, Decimal("2.13"))
        self.assertEqual(result.advised_rate, Decimal("81.36"))
        self.assertEqual(result.budget_status, "too_low")  # > 10% under €120

    def test_travel_excluded_when_distance_unknown(self):
        result = calculate(PricingInput(salary_month=6000, transport_type="car"))
        self.assertFalse(result.travel_known)
        self.assertEqual(result.advised_rate, Decimal("79.23"))

    def test_travel_from_distance(self):
        # 25 km × 2 × 214 days × €0.25 ÷ 12 = €222.92 / month ÷ (40 h × 13 ÷ 3) = €1.286 -> €1.29
        result = calculate(PricingInput(salary_month=6000, travel_distance_km=25, transport_type="car"))
        self.assertEqual(result.travel_per_hour, Decimal("1.29"))
        self.assertEqual(result.advised_rate, Decimal("80.52"))

    def test_client_pays_travel(self):
        result = calculate(PricingInput(salary_month=6000, travel_distance_km=25, client_pays_travel=True))
        self.assertEqual(result.travel_per_hour, Decimal("1.29"))  # still shown
        self.assertEqual(result.travel_in_tariff, Decimal("0.00"))  # but not charged
        self.assertEqual(result.advised_rate, Decimal("79.23"))

    def test_margin_limits(self):
        for margin in (-1, 26):
            with self.assertRaises(ValueError):
                PricingInput(salary_month=6000, margin=margin)

    def test_breakdown_groups_chain_operations(self):
        groups = calculate(PricingInput(salary_month=6000, travel_distance_km=25)).breakdown
        self.assertEqual([r["op"] for r in groups[-1]["rows"]], ["", "+", "+", "="])
        self.assertTrue(all(g["rows"][-1]["op"] == "=" for g in groups))

    def test_cost_steps_end_in_cost_price(self):
        result = calculate(PricingInput(salary_month=6000, hours_per_week=40, cost_factor=2))
        self.assertEqual([r["op"] for r in result.cost_steps], ["", "=", "×", "="])
        self.assertEqual(result.cost_steps[-1]["value"], str(result.cost_price))

    def test_remote_days_reduce_travel(self):
        # 3 office days: 50 km × 214 × 3 ÷ 5 × €0.25 ÷ (40 h × 52) = €0.77
        result = calculate(PricingInput(salary_month=6000, travel_distance_km=25, remote_days_per_week=2))
        self.assertEqual(result.travel_per_hour, Decimal("0.77"))

    def test_fully_remote_has_no_travel_costs(self):
        for transport in ("car", "ov"):
            result = calculate(PricingInput(salary_month=6000, travel_distance_km=25, transport_type=transport,
                                            remote_days_per_week=5))
            self.assertEqual(result.travel_per_hour, Decimal("0.00"))

    def test_manual_travel_uses_entered_amount(self):
        result = calculate(PricingInput(salary_month=6000, travel_distance_km=25, transport_type="manual",
                                        travel_per_hour_override="3.50"))
        self.assertEqual(result.travel_per_hour, Decimal("3.50"))
        self.assertEqual(result.travel_steps[-1]["value"], "3.50")

    def test_manual_travel_without_amount_is_unknown(self):
        result = calculate(PricingInput(salary_month=6000, travel_distance_km=25, transport_type="manual"))
        self.assertFalse(result.travel_known)  # the distance is not used for manual travel means
        self.assertEqual(result.travel_in_tariff, Decimal("0.00"))

    def test_negative_remote_days(self):
        with self.assertRaises(ValueError):
            PricingInput(salary_month=6000, remote_days_per_week=-1)

    def test_travel_steps_car(self):
        result = calculate(PricingInput(salary_month=6000, travel_distance_km=25, transport_type="car",
                                        remote_days_per_week=1))
        labels = [r["label"] for r in result.travel_steps]
        self.assertEqual(labels, ["Distance return trip", "Office days / year", "Tax-free rate / km",
                                  "Hours / year", "Travel costs / hour"])
        self.assertEqual(result.travel_steps[0]["value"], "50 km")
        self.assertEqual(result.travel_steps[1]["value"], "171.2")  # 214 × 4 ÷ 5
        self.assertEqual(result.travel_steps[-1]["value"], str(result.travel_per_hour))

    def test_travel_steps_ov(self):
        capped = calculate(PricingInput(salary_month=6000, travel_distance_km=60, transport_type="ov"))
        self.assertEqual([r["label"] for r in capped.travel_steps],
                         ["Travel costs / month", "Hours / month", "Travel costs / hour"])
        self.assertEqual(capped.travel_steps[0]["value"], "400.00")

    def test_no_travel_steps_when_distance_unknown(self):
        self.assertEqual(calculate(PricingInput(salary_month=6000)).travel_steps, [])

    def test_travel_left_out_of_breakdown_when_unknown_or_paid_by_client(self):
        for inp in (PricingInput(salary_month=6000),
                    PricingInput(salary_month=6000, travel_distance_km=25, client_pays_travel=True)):
            rows = calculate(inp).breakdown[-1]["rows"]
            self.assertEqual([r["op"] for r in rows], ["", "+", "="])

    def test_budget_status(self):
        self.assertEqual(calculate(PricingInput(salary_month=6000, proposed_rate=119, max_rate=120)).budget_status, "ok")
        self.assertEqual(calculate(PricingInput(salary_month=6000, proposed_rate=121, max_rate=120)).budget_status, "over")
        self.assertEqual(calculate(PricingInput(salary_month=6000)).budget_status, "unknown")


class TariffToSalaryTests(SimpleTestCase):
    def test_example_from_brief(self):
        # €120 max, €10 margin, factor 2.0, 40h -> €9,533.33 / month
        result = rate_to_salary(120, 10, 2.0, 40)
        self.assertEqual(result["cost_price"], Decimal("110.00"))
        self.assertEqual(result["hourly_wage"], Decimal("55.00"))
        self.assertEqual(result["weekly_salary"], Decimal("2200.00"))
        self.assertEqual(result["monthly_salary"], Decimal("9533.33"))


class TravelDistanceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @mock.patch.object(travel, "_http_json", return_value={"routes": [{"distance": 45853}]})
    def test_route_distance_uses_routing_api(self, http):
        result = travel.route_distance_km("Utrecht", "Amsterdam")  # both in the offline city table
        self.assertEqual(result, {"km": Decimal("45.9"), "source": "route"})
        http.assert_called_once()

    @mock.patch.object(travel, "_http_json", side_effect=OSError("offline"))
    def test_falls_back_to_estimate_when_offline(self, http):
        result = travel.route_distance_km("Utrecht", "Amsterdam")
        self.assertEqual(result["source"], "estimate")
        self.assertGreater(result["km"], 30)

    @mock.patch.object(travel, "_http_json", return_value=[])
    def test_unknown_location(self, http):
        self.assertIsNone(travel.route_distance_km("Nowhere-ville", "Amsterdam"))


class PricingApiTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))

    def test_calculate_endpoint(self):
        response = self.client.post(reverse("pricing:calculate"), json.dumps({"salary_month": 6000}), content_type="application/json")
        self.assertEqual(response.json()["result"]["advised_rate"], "79.23")

    def test_calculate_with_manual_budget_and_no_vacancy(self):
        response = self.client.post(reverse("pricing:calculate"), json.dumps({"salary_month": 6000, "max_rate": "80"}),
                                    content_type="application/json")
        result = response.json()["result"]
        self.assertEqual(result["budget_status"], "ok")  # €79.23 within €80
        self.assertEqual(result["room_per_hour"], "0.77")

    def test_calculate_rejects_margin_out_of_range(self):
        response = self.client.post(reverse("pricing:calculate"), json.dumps({"salary_month": 6000, "margin": 30}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_reverse_endpoint(self):
        response = self.client.post(reverse("pricing:reverse"), json.dumps({"max_rate": 120}), content_type="application/json")
        result = response.json()["result"]
        self.assertEqual(result["monthly_salary"], "9533.33")
        self.assertEqual(result["cost_steps"][-1]["value"], "110.00")
        self.assertEqual(result["hourly_steps"][-1]["value"], "55.00")
        self.assertEqual(result["salary_steps"][-1]["value"], "9533.33")

    @mock.patch("pricing.views.route_distance_km", return_value={"km": Decimal("45.9"), "source": "route"})
    def test_distance_endpoint(self, route):
        response = self.client.get(reverse("pricing:distance"), {"origin": "Utrecht", "destination": "Amsterdam"})
        self.assertEqual(response.json()["km"], "45.9")

    def test_calculator_prefills_candidate(self):
        from candidates.models import Candidate
        candidate = Candidate.objects.create(first_name="Sanne", last_name="Smit", expected_salary_month=5100)
        response = self.client.get(reverse("pricing:calculator"), {"candidate": candidate.pk})
        self.assertContains(response, 'value="5100.00"')

    def test_calculator_prefills_candidate_at_a_vacancy(self):
        from candidates.models import Candidate, CandidateVacancy
        from clients.models import Client, Vacancy
        company = Client.objects.create(name="ACME")
        first, second = (Vacancy.objects.create(client=company, title=t, max_rate_per_hour=90) for t in ("A", "B"))
        candidate = Candidate.objects.create(first_name="Sanne", last_name="Smit", expected_salary_month=5100)
        CandidateVacancy.objects.create(candidate=candidate, vacancy=first, travel_distance_km=10)
        CandidateVacancy.objects.create(candidate=candidate, vacancy=second, travel_distance_km=33)
        response = self.client.get(reverse("pricing:calculator"), {"candidate": candidate.pk, "vacancy": second.pk})
        self.assertEqual(response.context["initial"]["vacancy_id"], second.pk)
        self.assertContains(response, 'value="33.0"')

    def test_calculator_does_not_swap_in_another_vacancy(self):
        from candidates.models import Candidate, CandidateVacancy
        from clients.models import Client, Vacancy
        company = Client.objects.create(name="ACME")
        linked, unlinked = (Vacancy.objects.create(client=company, title=t, max_rate_per_hour=90) for t in ("A", "B"))
        candidate = Candidate.objects.create(first_name="Sanne", last_name="Smit", expected_salary_month=5100)
        CandidateVacancy.objects.create(candidate=candidate, vacancy=linked, travel_distance_km=10)
        response = self.client.get(reverse("pricing:calculator"), {"candidate": candidate.pk, "vacancy": unlinked.pk})
        self.assertIsNone(response.context["initial"]["vacancy_id"])
        self.assertIsNone(response.context["initial"]["travel_distance_km"])
