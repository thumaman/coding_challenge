import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .engine import PricingInput, calculate, rate_to_salary


class SalaryToRateTests(SimpleTestCase):
    def test_example_from_brief(self):
        # €6000, 40h, factor 2.0, €2.13 travel, €10 margin -> €81.36
        result = calculate(PricingInput(
            salary_month=6000, hours_per_week=40, cost_factor=2.0, margin=10,
            travel_known=True, travel_per_hour_override=Decimal("2.13"), max_rate=120,
        ))
        self.assertEqual(result.hourly_wage, Decimal("34.62"))
        self.assertEqual(result.cost_price, Decimal("69.23"))
        self.assertEqual(result.all_in_cost, Decimal("71.36"))
        self.assertEqual(result.advised_rate, Decimal("81.36"))
        self.assertEqual(result.budget_status, "too_low")  # > 10% under €120

    def test_travel_excluded_when_unknown(self):
        result = calculate(PricingInput(salary_month=6000, travel_known=False, travel_distance_km=50, transport_type="car"))
        self.assertEqual(result.travel_per_hour, Decimal("0.00"))
        self.assertEqual(result.advised_rate, Decimal("79.23"))

    def test_remote_days_lower_travel_cost(self):
        base = dict(salary_month=5000, travel_known=True, travel_distance_km=30, transport_type="car")
        office = calculate(PricingInput(**base, remote_days=0))
        hybrid = calculate(PricingInput(**base, remote_days=2))
        self.assertLess(hybrid.travel_per_hour, office.travel_per_hour)

    def test_budget_status(self):
        self.assertEqual(calculate(PricingInput(salary_month=6000, proposed_rate=119, max_rate=120)).budget_status, "ok")
        self.assertEqual(calculate(PricingInput(salary_month=6000, proposed_rate=121, max_rate=120)).budget_status, "over")
        self.assertEqual(calculate(PricingInput(salary_month=6000)).budget_status, "unknown")


class RateToSalaryTests(SimpleTestCase):
    def test_example_from_brief(self):
        # €120 max, €10 margin, factor 2.0, 40h -> €9,533.33 / month
        result = rate_to_salary(120, 10, 2.0, 40)
        self.assertEqual(result["cost_price"], Decimal("110.00"))
        self.assertEqual(result["hourly_wage"], Decimal("55.00"))
        self.assertEqual(result["weekly_salary"], Decimal("2200.00"))
        self.assertEqual(result["monthly_salary"], Decimal("9533.33"))


class PricingApiTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))

    def test_calculate_endpoint(self):
        response = self.client.post(reverse("pricing:calculate"), json.dumps({"salary_month": 6000}), content_type="application/json")
        self.assertEqual(response.json()["result"]["advised_rate"], "79.23")

    def test_reverse_endpoint(self):
        response = self.client.post(reverse("pricing:reverse"), json.dumps({"max_rate": 120}), content_type="application/json")
        self.assertEqual(response.json()["result"]["monthly_salary"], "9533.33")
