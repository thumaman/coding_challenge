from decimal import Decimal

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clients.models import Client, Vacancy

from .models import Candidate, CandidateDraft, CandidateVacancy

CANDIDATE = {
    "first_name": "Sanne", "last_name": "de Vries", "expected_salary_month": "6000",
    "hours_per_week": "40", "transport_type": "car", "remote_days_per_week": "0", "cost_factor": "2.0",
    "margin_per_hour": "10",
}


def links(*rows, initial=0):
    """POST data for the vacancy rows (CandidateVacancyFormSet, prefix "links"); each row is a dict of fields."""
    data = {"links-TOTAL_FORMS": str(len(rows)), "links-INITIAL_FORMS": str(initial)}
    for i, row in enumerate(rows):
        data.update({f"links-{i}-{k}": v for k, v in {"status": "considered", **row}.items()})
    return data


def make_vacancy(title="Engineer", max_rate=100, **kwargs):
    company, _ = Client.objects.get_or_create(name="ACME", defaults={"city": "Amsterdam"})
    return Vacancy.objects.create(client=company, title=title, max_rate_per_hour=max_rate, **kwargs)


class CandidateCrudTests(TestCase):
    # TODO(Vidic): extend (filters, validation, over-budget badge)
    def setUp(self):
        self.client.force_login(User.objects.create_user("recruiter"))
        self.vacancy = make_vacancy()
        self.valid = {**CANDIDATE, **links({"vacancy": self.vacancy.pk})}

    def test_list_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("candidates:list")).status_code, 302)

    def test_create_page_renders(self):
        response = self.client.get(reverse("candidates:create"))
        self.assertContains(response, 'id="forward-form"')
        self.assertContains(response, "data-autosave")

    def test_create_redirects_to_detail(self):
        response = self.client.post(reverse("candidates:create"), self.valid)
        candidate = Candidate.objects.get()
        self.assertRedirects(response, reverse("candidates:detail", args=[candidate.pk]))
        self.assertEqual(candidate.links.get().pricing.advised_rate, Decimal("79.23"))

    def test_client_pays_travel_toggle_leaves_travel_out(self):
        data = {**CANDIDATE, **links({"vacancy": self.vacancy.pk, "travel_distance_km": "50", "client_pays_travel": "on"})}
        self.client.post(reverse("candidates:create"), data)
        link = CandidateVacancy.objects.get()
        self.assertTrue(link.client_pays_travel)
        self.assertEqual(link.pricing.travel_in_tariff, 0)
        self.assertEqual(link.pricing.advised_rate, Decimal("79.23"))

    def test_at_least_one_vacancy_is_required(self):
        response = self.client.post(reverse("candidates:create"), {**CANDIDATE, **links()})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["formset"].non_form_errors())
        self.assertFalse(Candidate.objects.exists())

    def test_several_vacancies_each_with_their_own_tariff(self):
        far = make_vacancy("Far away", max_rate=120)
        data = {**CANDIDATE, **links(
            {"vacancy": self.vacancy.pk, "travel_distance_km": "0"},
            {"vacancy": far.pk, "travel_distance_km": "80", "proposed_rate": "110"},
        )}
        self.client.post(reverse("candidates:create"), data)
        candidate = Candidate.objects.get()
        self.assertEqual(set(candidate.vacancies.all()), {self.vacancy, far})
        near_link, far_link = candidate.links.all()
        self.assertGreater(far_link.pricing.advised_rate, near_link.pricing.advised_rate)
        self.assertEqual(far_link.pricing.final_rate, Decimal("110"))

    def test_same_vacancy_twice_is_rejected(self):
        data = {**CANDIDATE, **links({"vacancy": self.vacancy.pk}, {"vacancy": self.vacancy.pk})}
        response = self.client.post(reverse("candidates:create"), data)
        self.assertTrue(response.context["formset"].non_form_errors())
        self.assertFalse(Candidate.objects.exists())

    def test_remove_a_vacancy(self):
        other = make_vacancy("Other")
        candidate = Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=5000)
        keep = CandidateVacancy.objects.create(candidate=candidate, vacancy=self.vacancy, travel_distance_km=10)
        gone = CandidateVacancy.objects.create(candidate=candidate, vacancy=other, travel_distance_km=10)
        data = {**CANDIDATE, **links(
            {"id": keep.pk, "vacancy": self.vacancy.pk, "travel_distance_km": "10"},
            {"id": gone.pk, "vacancy": other.pk, "travel_distance_km": "10", "DELETE": "on"},
            initial=2,
        )}
        response = self.client.post(reverse("candidates:update", args=[candidate.pk]), data)
        self.assertRedirects(response, reverse("candidates:detail", args=[candidate.pk]))
        self.assertEqual(list(candidate.vacancies.all()), [self.vacancy])

    def test_detail_shows_a_card_per_vacancy(self):
        candidate = Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=5000)
        CandidateVacancy.objects.create(candidate=candidate, vacancy=self.vacancy, travel_distance_km=10)
        CandidateVacancy.objects.create(candidate=candidate, vacancy=make_vacancy("Analyst"), travel_distance_km=10)
        response = self.client.get(reverse("candidates:detail", args=[candidate.pk]))
        self.assertEqual(len(response.context["links"]), 2)
        self.assertContains(response, "Analyst")

    def test_invalid_form_rerenders_page(self):
        response = self.client.post(reverse("candidates:create"), {**self.valid, "first_name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Candidate.objects.exists())

    def test_update_and_delete(self):
        candidate = Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=5000)
        self.assertContains(self.client.get(reverse("candidates:update", args=[candidate.pk])), 'value="A"')
        response = self.client.post(reverse("candidates:update", args=[candidate.pk]), {**self.valid, "first_name": "Bram"})
        self.assertRedirects(response, reverse("candidates:detail", args=[candidate.pk]))
        candidate.refresh_from_db()
        self.assertEqual(candidate.first_name, "Bram")
        response = self.client.post(reverse("candidates:delete", args=[candidate.pk]))
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Candidate.objects.exists())

    def test_margin_must_be_between_0_and_25(self):
        response = self.client.post(reverse("candidates:create"), {**self.valid, "margin_per_hour": "30"})
        self.assertIn("margin_per_hour", response.context["form"].errors)

    @mock.patch("candidates.models.route_distance_km", return_value={"km": Decimal("45.9"), "source": "route"})
    def test_travel_distance_calculated_automatically(self, route):
        self.client.post(reverse("candidates:create"), {**self.valid, "city": "Utrecht"})
        self.assertEqual(CandidateVacancy.objects.get().travel_distance_km, Decimal("45.9"))
        route.assert_called_once_with("Utrecht", "Amsterdam")

    @mock.patch("candidates.models.route_distance_km", return_value={"km": Decimal("12.0"), "source": "route"})
    def test_moving_house_recalculates_every_distance(self, route):
        candidate = Candidate.objects.create(first_name="A", last_name="B", city="Utrecht", expected_salary_month=5000)
        link = CandidateVacancy.objects.create(candidate=candidate, vacancy=self.vacancy, travel_distance_km=45)
        data = {**CANDIDATE, "city": "Haarlem",
                **links({"id": link.pk, "vacancy": self.vacancy.pk, "travel_distance_km": "45.0"}, initial=1)}
        self.client.post(reverse("candidates:update", args=[candidate.pk]), data)
        link.refresh_from_db()
        self.assertEqual(link.travel_distance_km, Decimal("12.0"))

    def test_data_endpoint(self):
        candidate = Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=6000)
        CandidateVacancy.objects.create(candidate=candidate, vacancy=self.vacancy)
        CandidateVacancy.objects.create(candidate=candidate, vacancy=make_vacancy("Cheap", max_rate=60))
        data = self.client.get(reverse("candidates:data")).json()["data"]
        # One row per vacancy
        self.assertEqual([row["name"] for row in data], ["A B", "A B"])
        self.assertEqual([row["link"]["rate"] for row in data], ["79.23", "79.23"])
        self.assertEqual([row["link"]["budget_status"] for row in data], ["too_low", "over"])

    def test_data_endpoint_candidate_without_vacancy(self):
        Candidate.objects.create(first_name="A", last_name="B", expected_salary_month=6000)
        data = self.client.get(reverse("candidates:data")).json()["data"]
        self.assertEqual([row["link"] for row in data], [None])

    def test_data_endpoint_vacancy_filter(self):
        other = make_vacancy("Other")
        for name, vacancy in (("In", self.vacancy), ("Out", other)):
            candidate = Candidate.objects.create(first_name=name, last_name="X", expected_salary_month=5000)
            CandidateVacancy.objects.create(candidate=candidate, vacancy=vacancy)
        CandidateVacancy.objects.create(candidate=Candidate.objects.get(first_name="In"), vacancy=other)
        data = self.client.get(reverse("candidates:data"), {"vacancy": self.vacancy.pk}).json()["data"]
        # Only the row for the filtered vacancy, not the candidate's other vacancies
        self.assertEqual([(row["name"], row["link"]["vacancy"]) for row in data], [("In X", str(self.vacancy))])


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
        self.autosave(**CANDIDATE)
        self.assertFalse(Candidate.objects.exists())
        self.assertEqual(self.client.get(reverse("candidates:data")).json()["data"], [])

    def test_save_as_draft_button(self):
        response = self.client.post(reverse("candidates:create"), {"first_name": "Half", "action": "draft"})
        self.assertRedirects(response, reverse("candidates:list"))
        self.assertEqual(CandidateDraft.objects.get().data, {"first_name": "Half"})
        self.assertFalse(Candidate.objects.exists())

    def test_continue_draft_prefills_and_save_removes_it(self):
        vacancy = make_vacancy("Data Engineer")
        draft_id = self.autosave(first_name="Sanne", desired_role="Engineer", **links({"vacancy": vacancy.pk}))["id"]
        response = self.client.get(reverse("candidates:create"), {"draft": draft_id})
        self.assertContains(response, 'value="Engineer"')
        self.assertEqual(len(response.context["link_rows"]), 1)  # the vacancy row comes back too
        self.assertContains(response, "Data Engineer")
        self.client.post(reverse("candidates:create"), {**CANDIDATE, **links({"vacancy": vacancy.pk}), "draft": draft_id})
        self.assertTrue(Candidate.objects.exists())
        self.assertFalse(CandidateDraft.objects.exists())

    def test_invalid_submit_keeps_a_draft(self):
        self.client.post(reverse("candidates:create"), {**CANDIDATE, **links(), "first_name": ""})
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
