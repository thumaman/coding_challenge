from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, UpdateView

from clients.models import Vacancy
from clients.views import advisor_panel_context
from core.modals import ModalDeleteMixin, ModalFormMixin

from .forms import CandidateForm
from .models import Candidate


def candidate_list(request):
    return render(request, "candidates/list.html", {
        "statuses": Candidate.Status.choices,
        "vacancies": Vacancy.objects.select_related("client"),
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


class CandidateFormMixin(ModalFormMixin):
    model = Candidate
    form_class = CandidateForm
    template_name = "candidates/_form.html"


class CandidateCreateView(CandidateFormMixin, CreateView):
    modal_title = _("New candidate")
    success_message = _("Candidate added.")


class CandidateUpdateView(CandidateFormMixin, UpdateView):
    modal_title = _("Edit candidate")
    success_message = _("Candidate saved.")


class CandidateDeleteView(ModalDeleteMixin, DeleteView):
    model = Candidate
    modal_title = _("Delete candidate")
    success_message = _("Candidate deleted.")


def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate.objects.select_related("vacancy__client"), pk=pk)
    return render(request, "candidates/detail.html", advisor_panel_context(candidate))
