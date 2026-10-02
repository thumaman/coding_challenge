from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, UpdateView

from candidates.models import Candidate
from core.drafts import DraftCreateMixin, DraftDeleteView, draft_autosave_view, draft_list_view
from core.modals import ModalDeleteMixin
from pricing import constants as C

from . import matching
from .advisor import suggest_tweaks
from .forms import ClientForm, VacancyForm
from .models import Client, Vacancy, VacancyDraft


# ---------- Vacancies ----------

def vacancy_list(request):
    return render(request, "clients/vacancy_list.html", {
        "clients": Client.objects.all(),
        "draft_count": request.user.vacancy_drafts.count(),
    })


def vacancy_data(request):
    """JSON for the vacancies DataTable: open vacancies only, unless ?all=1."""
    # TODO(Ivan): filters (client, max rate range) via request.GET
    qs = Vacancy.objects.select_related("client")
    if not request.GET.get("all"):
        qs = qs.filter(is_open=True)
    rows = []
    for v in qs:
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


class VacancyFormMixin:
    """Full-page vacancy form, in the same style as the candidate page."""

    model = Vacancy
    form_class = VacancyForm
    template_name = "clients/vacancy_form.html"
    success_message = ""

    def get_context_data(self, **kwargs):
        return super().get_context_data(C=C, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, self.success_message)
        return redirect("clients:detail", pk=self.object.pk)


class VacancyCreateView(DraftCreateMixin, VacancyFormMixin, CreateView):
    success_message = _("Vacancy added.")
    draft_model = VacancyDraft
    draft_redirect_url = "clients:vacancy_list"

    def get_initial(self):
        initial = super().get_initial()
        if client := self.request.GET.get("client"):  # "+ Vacancy" on the clients page, or back from "+ New client"
            initial["client"] = client
        return initial


class VacancyUpdateView(VacancyFormMixin, UpdateView):
    success_message = _("Vacancy saved.")


class VacancyDeleteView(ModalDeleteMixin, DeleteView):
    model = Vacancy
    modal_title = _("Delete vacancy")
    success_message = _("Vacancy deleted.")


vacancy_draft_autosave = draft_autosave_view(VacancyDraft)

vacancy_draft_list = draft_list_view(
    "vacancy_drafts",
    heading=_("Draft vacancies"),
    empty_text=_("No drafts. Unfinished new vacancies are saved here automatically."),
    continue_url=reverse_lazy("clients:create"),
    delete_url_name="clients:draft_delete",
)


class VacancyDraftDeleteView(DraftDeleteView):
    drafts_attr = "vacancy_drafts"


def vacancy_detail(request, pk):
    vacancy = get_object_or_404(Vacancy.objects.select_related("client"), pk=pk)
    candidates = (Candidate.objects.exclude(status__in=[Candidate.Status.INACTIVE, Candidate.Status.PLACED])
                  .prefetch_related("links__vacancy__client"))
    ranked = [
        {"candidate": c, "score": s, "pricing": c.pricing_for(vacancy), "link": c.link_for(vacancy)}
        for c, s in matching.rank_candidates(vacancy, candidates)
    ]
    return render(request, "clients/vacancy_detail.html", {
        "vacancy": vacancy, "ranked": ranked, "max_score": matching.MAX_SCORE,
    })


# ---------- Clients (companies) ----------

def client_list(request):
    clients = Client.objects.prefetch_related("vacancies")
    return render(request, "clients/client_list.html", {
        "clients": clients,
        "industries": sorted({c.industry for c in clients if c.industry}),
        "cities": sorted({c.city for c in clients if c.city}),
    })


class ClientFormMixin:
    """Full-page client form. ?next= returns to where "+ New client" was clicked (e.g. the vacancy form)."""

    model = Client
    form_class = ClientForm
    template_name = "clients/client_form.html"
    success_message = ""

    def next_url(self):
        url = self.request.POST.get("next") or self.request.GET.get("next")
        if url and url_has_allowed_host_and_scheme(url, {self.request.get_host()}):
            return url
        return None

    def get_context_data(self, **kwargs):
        return super().get_context_data(next=self.next_url(), **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, self.success_message)
        if url := self.next_url():
            separator = "&" if "?" in url else "?"
            return redirect(f"{url}{separator}client={self.object.pk}")
        return redirect("clients:client_list")


class ClientCreateView(ClientFormMixin, CreateView):
    success_message = _("Client added.")


class ClientUpdateView(ClientFormMixin, UpdateView):
    success_message = _("Client saved.")


class ClientDeleteView(ModalDeleteMixin, DeleteView):
    model = Client
    modal_title = _("Delete client")
    success_message = _("Client deleted.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        count = self.object.vacancies.count()
        if count:
            context["warning"] = _("Its %(count)s vacancies are deleted too.") % {"count": count}
        return context


# ---------- AI advisor ----------

def advisor_panel_context(candidate):
    """Candidate detail: one entry per vacancy the candidate is considered for, with advisor options."""
    links = list(candidate.links.all())
    return {"candidate": candidate, "links": [{"link": link, "options": suggest_tweaks(link)} for link in links]}
