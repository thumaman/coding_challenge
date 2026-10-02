from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from candidates.models import Candidate, CandidateVacancy

from .advisor import suggest_tweaks
from .matching import MAX_SCORE, score
from .models import Client, Vacancy, VacancyDraft


class AdvisorTests(TestCase):
    # TODO(Ivan): extend (combined options, Claude ranking with a mocked client)
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))
        company = Client.objects.create(name="ACME")
        self.vacancy = Vacancy.objects.create(client=company, title="Data Engineer", max_rate_per_hour=80)
        # €6000 -> advised €79.23 without travel; with 50 km by car it goes over €80
        self.candidate = Candidate.objects.create(
            first_name="A", last_name="B", expected_salary_month=6000, transport_type="car",
        )
        self.link = CandidateVacancy.objects.create(candidate=self.candidate, vacancy=self.vacancy, travel_distance_km=50)

    @mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_solver_brings_candidate_within_budget(self):
        self.assertEqual(self.link.pricing.budget_status, "over")
        options = suggest_tweaks(self.link)
        self.assertTrue(options)
        for option in options:
            self.assertLessEqual(Decimal(option["new_rate"]), Decimal(80))

    @mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_client_pays_travel_option(self):
        option = next(o for o in suggest_tweaks(self.link) if o["key"] == "client_travel")
        self.assertEqual(option["changes"], {"client_pays_travel": "True"})

    @mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""})
    def test_detail_shows_advisor_without_apply_button(self):
        response = self.client.get(reverse("candidates:detail", args=[self.candidate.pk]))
        self.assertContains(response, "Advisor Insights")
        self.assertContains(response, "Lower salary")
        self.assertNotContains(response, "/advisor/")

    def test_vacancy_detail_marks_linked_candidates(self):
        response = self.client.get(reverse("clients:detail", args=[self.vacancy.pk]))
        self.assertEqual(response.context["ranked"][0]["link"], self.link)

    def test_match_score_range(self):
        result = score(self.candidate, self.vacancy)
        self.assertTrue(0 <= result["total"] <= MAX_SCORE)


VACANCY = {
    "title": "Data Engineer", "max_rate_per_hour": "100", "hours_per_week": "40", "remote_days_allowed": "1",
    "is_open": "on",
}


class VacancyDataTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))
        company = Client.objects.create(name="ACME")
        Vacancy.objects.create(client=company, title="Open", max_rate_per_hour=80)
        Vacancy.objects.create(client=company, title="Closed", max_rate_per_hour=80, is_open=False)

    def titles(self, **params):
        return {r["title"] for r in self.client.get(reverse("clients:data"), params).json()["data"]}

    def test_open_vacancies_by_default(self):
        self.assertEqual(self.titles(), {"Open"})

    def test_all_vacancies_with_filter(self):
        self.assertEqual(self.titles(all=1), {"Open", "Closed"})


class VacancyPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("recruiter")
        self.client.force_login(self.user)
        self.company = Client.objects.create(name="ACME", city="Utrecht")

    def test_create_page_renders_with_drafts(self):
        response = self.client.get(reverse("clients:create"))
        self.assertContains(response, 'id="vacancy-form"')
        self.assertContains(response, "data-autosave")

    def test_client_is_prefilled(self):
        response = self.client.get(reverse("clients:create"), {"client": self.company.pk})
        self.assertEqual(str(response.context["form"]["client"].value()), str(self.company.pk))

    def test_create_redirects_to_detail(self):
        response = self.client.post(reverse("clients:create"), {**VACANCY, "client": self.company.pk})
        vacancy = Vacancy.objects.get()
        self.assertRedirects(response, reverse("clients:detail", args=[vacancy.pk]))
        self.assertTrue(vacancy.is_open)

    def test_invalid_submit_keeps_a_draft(self):
        response = self.client.post(reverse("clients:create"), {**VACANCY, "client": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VacancyDraft.objects.get().data["title"], "Data Engineer")

    def test_draft_flow(self):
        draft_id = self.client.post(reverse("clients:draft_autosave"), {"title": "Half", "client": self.company.pk}).json()["id"]
        draft = VacancyDraft.objects.get()
        self.assertEqual((draft.title, draft.subtitle), ("Half", "ACME"))
        self.assertContains(self.client.get(reverse("clients:drafts")), "Half")
        self.assertContains(self.client.get(reverse("clients:create"), {"draft": draft_id}), 'value="Half"')
        self.client.post(reverse("clients:create"), {**VACANCY, "client": self.company.pk, "draft": draft_id})
        self.assertTrue(Vacancy.objects.exists())
        self.assertFalse(VacancyDraft.objects.exists())

    def test_save_as_draft_button(self):
        response = self.client.post(reverse("clients:create"), {"title": "Later", "action": "draft"})
        self.assertRedirects(response, reverse("clients:vacancy_list"))
        self.assertFalse(Vacancy.objects.exists())
        self.assertEqual(self.client.get(reverse("clients:vacancy_list")).context["draft_count"], 1)

    def test_other_users_draft_is_not_accessible(self):
        draft = VacancyDraft.objects.create(owner=User.objects.create_user("other"), data={"title": "X"})
        self.assertEqual(self.client.get(reverse("clients:create"), {"draft": draft.pk}).status_code, 404)
        self.assertEqual(self.client.post(reverse("clients:draft_delete", args=[draft.pk])).status_code, 404)

    def test_update(self):
        vacancy = Vacancy.objects.create(client=self.company, title="Old", max_rate_per_hour=90)
        self.assertContains(self.client.get(reverse("clients:update", args=[vacancy.pk])), 'value="Old"')
        self.client.post(reverse("clients:update", args=[vacancy.pk]), {**VACANCY, "client": self.company.pk})
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.title, "Data Engineer")


class ClientPageTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))

    def test_create(self):
        response = self.client.post(reverse("clients:client_create"), {"name": "ACME", "industry": "Tech"})
        self.assertRedirects(response, reverse("clients:client_list"))
        self.assertEqual(Client.objects.get().industry, "Tech")

    def test_create_returns_to_next_with_the_new_client(self):
        response = self.client.post(reverse("clients:client_create"), {"name": "ACME", "next": "/clients/vacancies/new/?draft=3"})
        self.assertRedirects(response, f"/clients/vacancies/new/?draft=3&client={Client.objects.get().pk}",
                             fetch_redirect_response=False)

    def test_next_must_stay_on_this_site(self):
        response = self.client.post(reverse("clients:client_create"), {"name": "ACME", "next": "https://evil.example"})
        self.assertRedirects(response, reverse("clients:client_list"))

    def test_name_is_required(self):
        response = self.client.post(reverse("clients:client_create"), {"name": ""})
        self.assertTrue(response.context["form"].errors)

    def test_update_and_delete(self):
        company = Client.objects.create(name="ACME")
        Vacancy.objects.create(client=company, title="Dev", max_rate_per_hour=90)
        self.client.post(reverse("clients:client_update", args=[company.pk]), {"name": "ACME BV"})
        company.refresh_from_db()
        self.assertEqual(company.name, "ACME BV")
        self.assertContains(self.client.get(reverse("clients:client_delete", args=[company.pk])), "vacancies are deleted too")
        self.assertTrue(self.client.post(reverse("clients:client_delete", args=[company.pk])).json()["ok"])
        self.assertFalse(Vacancy.objects.exists())

    def test_list_has_filters(self):
        Client.objects.create(name="ACME", industry="Tech", city="Utrecht")
        response = self.client.get(reverse("clients:client_list"))
        self.assertContains(response, 'id="client-filters"')
        self.assertEqual(response.context["industries"], ["Tech"])
