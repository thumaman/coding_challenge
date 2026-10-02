import json
import re

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, UpdateView

from clients.models import Vacancy
from clients.views import advisor_panel_context
from core.drafts import DraftCreateMixin, DraftDeleteView, draft_autosave_view, draft_list_view
from core.modals import ModalDeleteMixin
from pricing import constants as C
from pricing.views import calculator_i18n

from .forms import CandidateForm, CandidateVacancyFormSet
from .models import Candidate, CandidateDraft


def candidate_list(request):
    return render(request, "candidates/list.html", {
        "statuses": Candidate.Status.choices,
        "vacancies": Vacancy.objects.select_related("client"),
        "draft_count": request.user.candidate_drafts.count(),
    })


def candidate_data(request):
    """JSON for the candidates DataTable (filters via query string): one row per vacancy a candidate is
    considered for; candidates without a vacancy get a single row."""
    qs = Candidate.objects.prefetch_related("links__vacancy__client")
    if status := request.GET.get("status"):
        qs = qs.filter(status=status)
    vacancy = request.GET.get("vacancy")
    if vacancy:
        qs = qs.filter(vacancies=vacancy).distinct()

    rows = []
    for c in qs:
        candidate = {
            "id": c.pk,
            "name": c.full_name,
            "role": c.desired_role,
            "status": c.get_status_display(),
            "salary": str(c.expected_salary_month),
            "hours": c.hours_per_week,
            "remote": c.remote_days_per_week,
            "urls": {
                "detail": reverse("candidates:detail", args=[c.pk]),
                "update": reverse("candidates:update", args=[c.pk]),
                "delete": reverse("candidates:delete", args=[c.pk]),
            },
        }
        links = [link for link in c.links.all() if not vacancy or str(link.vacancy_id) == vacancy]
        if not links:
            rows.append({**candidate, "link": None})
        for link in links:
            p = link.pricing
            rows.append({**candidate, "link": {
                "vacancy": str(link.vacancy),
                "url": reverse("clients:detail", args=[link.vacancy_id]),
                "status": link.get_status_display(),
                "rate": str(p.final_rate),
                "max_rate": str(p.max_rate),
                "budget_status": p.budget_status,
            }})
    return JsonResponse({"data": rows})


def _link_rows_from_draft(data):
    """Formset initial for the vacancy rows in a draft: {"links-0-vacancy": "3", ...} -> [{"vacancy": "3", ...}]."""
    rows = {}
    for key, value in data.items():
        if match := re.fullmatch(r"links-(\d+)-(\w+)", key):
            rows.setdefault(int(match[1]), {})[match[2]] = value
    return [row for _i, row in sorted(rows.items()) if row.get("vacancy") and not row.get("DELETE")]


class CandidateFormMixin:
    """Full-page candidate form, laid out like the calculator with the live tariff on top.

    The vacancies the candidate is considered for are a formset (CandidateVacancyFormSet, prefix "links"):
    one row per vacancy with its own travel distance, travel toggle and proposed tariff.
    """

    model = Candidate
    form_class = CandidateForm
    template_name = "candidates/form.html"
    success_message = ""

    # Candidate field -> pricing API field (read by calculator.js via data-field-map)
    PRICING_FIELD_MAP = {
        "expected_salary_month": "salary_month",
        "margin_per_hour": "margin",
        "city": "home_location",
    }

    @cached_property
    def formset(self):
        kwargs = {"instance": self.object or Candidate(), "prefix": "links"}
        if self.request.method == "POST":
            return CandidateVacancyFormSet(self.request.POST, **kwargs)
        draft = self.get_draft() if hasattr(self, "get_draft") else None
        initial = _link_rows_from_draft(draft.data) if draft else []
        formset = CandidateVacancyFormSet(initial=initial, **kwargs)
        formset.extra = len(initial)
        return formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vacancies = Vacancy.objects.select_related("client")
        by_pk = {str(v.pk): v for v in vacancies}
        linked = set(self.object.links.values_list("vacancy_id", flat=True)) if self.object else set()
        context.update(
            # The picker offers open vacancies; ones already linked stay visible even when closed
            vacancies=[v for v in vacancies if v.is_open or v.pk in linked],
            formset=self.formset,
            link_rows=[(f, by_pk.get(str(f["vacancy"].value()))) for f in self.formset.forms],
            C=C,
            i18n=calculator_i18n(),
            field_map_json=json.dumps(self.PRICING_FIELD_MAP),
        )
        return context

    def form_valid(self, form):
        if not self.formset.is_valid():
            return self.form_invalid(form)
        city_changed = form.instance.pk is not None and "city" in form.changed_data
        with transaction.atomic():
            self.object = form.save()
            self.formset.instance = self.object
            self.formset.save_links(city_changed=city_changed)
        messages.success(self.request, self.success_message)
        return redirect("candidates:detail", pk=self.object.pk)

    def form_invalid(self, form):
        self.formset.is_valid()  # also show the vacancy rows' errors
        return super().form_invalid(form)


class CandidateCreateView(DraftCreateMixin, CandidateFormMixin, CreateView):
    success_message = _("Candidate added.")
    draft_model = CandidateDraft
    draft_redirect_url = "candidates:list"


class CandidateUpdateView(CandidateFormMixin, UpdateView):
    success_message = _("Candidate saved.")


draft_autosave = draft_autosave_view(CandidateDraft)

draft_list = draft_list_view(
    "candidate_drafts",
    heading=_("Draft candidates"),
    empty_text=_("No drafts. Unfinished new candidates are saved here automatically."),
    continue_url=reverse_lazy("candidates:create"),
    delete_url_name="candidates:draft_delete",
)


class CandidateDraftDeleteView(DraftDeleteView):
    drafts_attr = "candidate_drafts"


class CandidateDeleteView(ModalDeleteMixin, DeleteView):
    model = Candidate
    modal_title = _("Delete candidate")
    success_message = _("Candidate deleted.")


def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate.objects.prefetch_related("links__vacancy__client"), pk=pk)
    return render(request, "candidates/detail.html", advisor_panel_context(candidate))
