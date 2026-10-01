from decimal import Decimal

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clients.models import Client, Vacancy

from .models import Candidate, CandidateDraft

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

    def test_create_page_renders(self):
        response = self.client.get(reverse("candidates:create"))
        self.assertContains(response, 'id="forward-form"')
        self.assertContains(response, "data-autosave")

    def test_create_redirects_to_detail(self):
        response = self.client.post(reverse("candidates:create"), VALID)
        candidate = Candidate.objects.get()
        self.assertRedirects(response, reverse("candidates:detail", args=[candidate.pk]))
        self.assertEqual(candidate.pricing.advised_rate, Decimal("79.23"))

    def test_invalid_form_rerenders_page(self):
        response = self.client.post(reverse("candidates:create"), {**VALID, "first_name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Candidate.objects.exists())

    def test_update_and_delete(self):
        candidate = Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=5000)
        self.assertContains(self.client.get(reverse("candidates:update", args=[candidate.pk])), 'value="A"')
        response = self.client.post(reverse("candidates:update", args=[candidate.pk]), {**VALID, "first_name": "Bram"})
        self.assertRedirects(response, reverse("candidates:detail", args=[candidate.pk]))
        candidate.refresh_from_db()
        self.assertEqual(candidate.first_name, "Bram")
        response = self.client.post(reverse("candidates:delete", args=[candidate.pk]))
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Candidate.objects.exists())

    def test_margin_must_be_between_0_and_25(self):
        response = self.client.post(reverse("candidates:create"), {**VALID, "margin_per_hour": "30"})
        self.assertIn("margin_per_hour", response.context["form"].errors)

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


class CandidateDraftTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("recruiter")
        self.client.force_login(self.user)

    def autosave(self, **data):
        return self.client.post(reverse("candidates:draft_autosave"), data).json()

    def test_autosave_creates_then_updates_one_draft(self):
        first = self.autosave(first_name="Sanne")
        second = self.autosave(draft=first["id"], first_name="Sanne", last_name="de Vries")
        self.assertEqual(first["id"], second["id"])
        draft = CandidateDraft.objects.get()
        self.assertEqual(draft.owner, self.user)
        self.assertEqual(draft.title, "Sanne de Vries")
        self.assertNotIn("csrfmiddlewaretoken", draft.data)

    def test_drafts_are_not_candidates(self):
        self.autosave(**VALID)
        self.assertFalse(Candidate.objects.exists())
        self.assertEqual(self.client.get(reverse("candidates:data")).json()["data"], [])

    def test_save_as_draft_button(self):
        response = self.client.post(reverse("candidates:create"), {"first_name": "Half", "action": "draft"})
        self.assertRedirects(response, reverse("candidates:list"))
        self.assertEqual(CandidateDraft.objects.get().data, {"first_name": "Half"})
        self.assertFalse(Candidate.objects.exists())

    def test_continue_draft_prefills_and_save_removes_it(self):
        draft_id = self.autosave(first_name="Sanne", desired_role="Engineer")["id"]
        response = self.client.get(reverse("candidates:create"), {"draft": draft_id})
        self.assertContains(response, 'value="Engineer"')
        self.client.post(reverse("candidates:create"), {**VALID, "draft": draft_id})
        self.assertTrue(Candidate.objects.exists())
        self.assertFalse(CandidateDraft.objects.exists())

    def test_invalid_submit_keeps_a_draft(self):
        self.client.post(reverse("candidates:create"), {**VALID, "first_name": ""})
        self.assertEqual(CandidateDraft.objects.get().data["last_name"], "de Vries")

    def test_list_shows_own_draft_count(self):
        self.autosave(first_name="Mine")
        CandidateDraft.objects.create(owner=User.objects.create_user("other"), data={"first_name": "Theirs"})
        self.assertEqual(self.client.get(reverse("candidates:list")).context["draft_count"], 1)
        response = self.client.get(reverse("candidates:drafts"))
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")

    def test_other_users_draft_is_not_accessible(self):
        draft = CandidateDraft.objects.create(owner=User.objects.create_user("other"), data={"first_name": "X"})
        self.assertEqual(self.client.get(reverse("candidates:create"), {"draft": draft.pk}).status_code, 404)
        self.assertEqual(self.client.post(reverse("candidates:draft_autosave"), {"draft": draft.pk}).status_code, 404)
        self.assertEqual(self.client.post(reverse("candidates:draft_delete", args=[draft.pk])).status_code, 404)
        self.assertTrue(CandidateDraft.objects.exists())

    def test_delete_draft(self):
        draft_id = self.autosave(first_name="Gone")["id"]
        response = self.client.post(reverse("candidates:draft_delete", args=[draft_id]))
        self.assertTrue(response.json()["ok"])
        self.assertFalse(CandidateDraft.objects.exists())
