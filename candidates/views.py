import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from clients.models import Vacancy
from clients.views import advisor_panel_context
from core.modals import ModalDeleteMixin
from pricing import constants as C
from pricing.views import calculator_i18n

from .forms import CandidateForm
from .models import Candidate, CandidateDraft


def candidate_list(request):
    return render(request, "candidates/list.html", {
        "statuses": Candidate.Status.choices,
        "vacancies": Vacancy.objects.select_related("client"),
        "draft_count": request.user.candidate_drafts.count(),
    })


def candidate_data(request):
    """JSON for the candidates DataTable (filters via query string)."""
    qs = Candidate.objects.select_related("vacancy__client")
    if status := request.GET.get("status"):
        qs = qs.filter(status=status)
    if vacancy := request.GET.get("vacancy"):
        qs = qs.filter(vacancy_id=vacancy)
    over_only = request.GET.get("over") == "1"

    rows = []
    for c in qs:
        p = c.pricing
        if over_only and p.budget_status != "over":
            continue
        rows.append({
            "id": c.pk,
            "name": c.full_name,
            "role": c.desired_role,
            "status": c.get_status_display(),
            "salary": str(c.expected_salary_month),
            "hours": c.hours_per_week,
            "remote": c.remote_days_per_week,
            "vacancy": str(c.vacancy) if c.vacancy else "",
            "rate": str(p.final_rate),
            "max_rate": str(p.max_rate) if p.max_rate is not None else None,
            "budget_status": p.budget_status,
            "urls": {
                "detail": reverse("candidates:detail", args=[c.pk]),
                "update": reverse("candidates:update", args=[c.pk]),
                "delete": reverse("candidates:delete", args=[c.pk]),
            },
        })
    return JsonResponse({"data": rows})


class CandidateFormMixin:
    """Full-page candidate form, laid out like the calculator with the live tariff on top."""

    model = Candidate
    form_class = CandidateForm
    template_name = "candidates/form.html"
    success_message = ""

    # Candidate field -> pricing API field (read by calculator.js via data-field-map)
    PRICING_FIELD_MAP = {
        "expected_salary_month": "salary_month",
        "margin_per_hour": "margin",
        "vacancy": "vacancy_id",
        "city": "home_location",
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            vacancies=Vacancy.objects.select_related("client"),
            C=C,
            i18n=calculator_i18n(),
            field_map_json=json.dumps(self.PRICING_FIELD_MAP),
        )
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, self.success_message)
        return redirect("candidates:detail", pk=self.object.pk)


def _form_data(post):
    """POST data worth keeping in a draft (single values, without the bookkeeping fields)."""
    return {k: v for k, v in post.items() if k not in ("csrfmiddlewaretoken", "draft", "action")}


def _save_draft(request):
    """Create or update the current user's draft from the POSTed form (the id travels in the "draft" field)."""
    draft_id = request.POST.get("draft")
    draft = get_object_or_404(CandidateDraft, pk=draft_id, owner=request.user) if draft_id else \
        CandidateDraft(owner=request.user)
    draft.data = _form_data(request.POST)
    draft.save()
    return draft


class CandidateCreateView(CandidateFormMixin, CreateView):
    success_message = _("Candidate added.")

    def get_draft(self):
        draft_id = self.request.GET.get("draft") or self.request.POST.get("draft")
        if not draft_id:
            return None
        return get_object_or_404(CandidateDraft, pk=draft_id, owner=self.request.user)

    def get_initial(self):
        draft = self.get_draft() if self.request.method == "GET" else None
        return {**super().get_initial(), **(draft.data if draft else {})}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["draft"] = getattr(self, "draft", None) or self.get_draft()
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "draft":
            _save_draft(request)
            messages.success(request, _("Draft saved."))
            return redirect("candidates:list")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        draft = self.get_draft()
        response = super().form_valid(form)
        if draft:
            draft.delete()
        return response

    def form_invalid(self, form):
        self.draft = _save_draft(self.request)  # keep what was typed, even if the page is left now
        return super().form_invalid(form)


class CandidateUpdateView(CandidateFormMixin, UpdateView):
    success_message = _("Candidate saved.")


@require_POST
def draft_autosave(request):
    """Autosave from the new-candidate page (fetch while typing, sendBeacon when the page is left)."""
    draft = _save_draft(request)
    return JsonResponse({"ok": True, "id": draft.pk})


def draft_list(request):
    return render(request, "candidates/_drafts.html", {"drafts": request.user.candidate_drafts.all()})


class DraftDeleteView(ModalDeleteMixin, DeleteView):
    modal_title = _("Delete draft")
    success_message = _("Draft deleted.")

    def get_queryset(self):
        return self.request.user.candidate_drafts.all()


class CandidateDeleteView(ModalDeleteMixin, DeleteView):
    model = Candidate
    modal_title = _("Delete candidate")
    success_message = _("Candidate deleted.")


def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate.objects.select_related("vacancy__client"), pk=pk)
    return render(request, "candidates/detail.html", advisor_panel_context(candidate))
