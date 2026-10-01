import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from candidates.models import Candidate
from core.modals import ModalDeleteMixin, ModalFormMixin

from . import matching
from .advisor import suggest_tweaks
from .forms import VacancyForm
from .models import Client, Vacancy


# ---------- Vacancies ----------

def vacancy_list(request):
    return render(request, "clients/vacancy_list.html", {"clients": Client.objects.all()})


def vacancy_data(request):
    """JSON for the vacancies DataTable."""
    # TODO(Ivan): filters (client, open/closed, max rate range) via request.GET
    rows = []
    for v in Vacancy.objects.select_related("client"):
        rows.append({
            "id": v.pk,
            "title": v.title,
            "client": v.client.name,
            "city": v.city,
            "client_pays_travel": v.client_pays_travel,
            "max_rate": str(v.max_rate_per_hour),
            "hours": v.hours_per_week,
            "remote": v.remote_days_allowed,
            "is_open": v.is_open,
            "urls": {
                "detail": reverse("clients:detail", args=[v.pk]),
                "update": reverse("clients:update", args=[v.pk]),
                "delete": reverse("clients:delete", args=[v.pk]),
            },
        })
    return JsonResponse({"data": rows})


class VacancyCreateView(ModalFormMixin, CreateView):
    model = Vacancy
    form_class = VacancyForm
    modal_title = _("New vacancy")
    success_message = _("Vacancy added.")


class VacancyUpdateView(ModalFormMixin, UpdateView):
    model = Vacancy
    form_class = VacancyForm
    modal_title = _("Edit vacancy")
    success_message = _("Vacancy saved.")


class VacancyDeleteView(ModalDeleteMixin, DeleteView):
    model = Vacancy
    modal_title = _("Delete vacancy")
    success_message = _("Vacancy deleted.")


def vacancy_detail(request, pk):
    vacancy = get_object_or_404(Vacancy.objects.select_related("client"), pk=pk)
    candidates = Candidate.objects.exclude(status__in=[Candidate.Status.INACTIVE, Candidate.Status.PLACED])
    ranked = [
        {"candidate": c, "score": s, "pricing": c.pricing_for(vacancy)}
        for c, s in matching.rank_candidates(vacancy, candidates)
    ]
    return render(request, "clients/vacancy_detail.html", {"vacancy": vacancy, "ranked": ranked})


# ---------- Clients (companies) ----------

def client_list(request):
    # TODO(Ivan): full Client CRUD with the same DataTable + modal pattern as vacancies
    return render(request, "clients/client_list.html", {"clients": Client.objects.prefetch_related("vacancies")})


# ---------- AI advisor ----------

def advisor_panel_context(candidate):
    return {"candidate": candidate, "options": suggest_tweaks(candidate)}


VACANCY_TWEAK_FIELDS = {"vacancy.client_pays_travel"}


@require_POST
def apply_tweak(request, candidate_pk):
    """POST {"changes": {field: value}} -> apply to the candidate (or `vacancy.<field>` to its vacancy)."""
    candidate = get_object_or_404(Candidate.objects.select_related("vacancy"), pk=candidate_pk)
    try:
        changes = json.loads(request.POST.get("changes") or request.body or "{}")
        changes = changes.get("changes", changes)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "message": "Invalid changes"}, status=400)
    allowed = set(Candidate.PRICING_FIELD_MAP.values()) | VACANCY_TWEAK_FIELDS
    if not set(changes) <= allowed:
        return JsonResponse({"ok": False, "message": f"Field not allowed: {set(changes) - allowed}"}, status=400)
    for field, value in changes.items():
        if field.startswith("vacancy."):
            name = field.removeprefix("vacancy.")
            setattr(candidate.vacancy, name, candidate.vacancy._meta.get_field(name).to_python(value))
            candidate.vacancy.save()
        else:
            setattr(candidate, field, Candidate._meta.get_field(field).to_python(value))
    candidate.proposed_rate = None  # the advised tariff is recalculated from the new terms
    candidate.save()
    return JsonResponse({"ok": True, "message": _("Tweak applied to %(name)s.") % {"name": candidate.full_name}})
