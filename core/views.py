from decimal import Decimal

from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from candidates.models import Candidate
from clients.models import Vacancy


def dashboard(request):
    # TODO(Joseph): richer KPIs / charts. Pricing is computed in Python, fine for hackathon-sized data.
    candidates = list(Candidate.objects.select_related("vacancy").exclude(status=Candidate.Status.INACTIVE))
    results = [c.pricing for c in candidates]
    over_budget = sum(1 for r in results if r.budget_status == "over")
    margins = [r.margin for r in results]
    context = {
        "open_vacancies": Vacancy.objects.filter(is_open=True).count(),
        "active_candidates": len(candidates),
        "over_budget": over_budget,
        "avg_margin": (sum(margins, Decimal(0)) / len(margins)) if margins else Decimal(0),
        "recent_candidates": Candidate.objects.select_related("vacancy").order_by("-created_at")[:6],
    }
    return render(request, "core/dashboard.html", context)


@login_not_required
def manifest(request):
    return render(request, "core/manifest.webmanifest", content_type="application/manifest+json")


@login_not_required
@never_cache
def service_worker(request):
    # Served from the site root so the service worker can control every page.
    response = render(request, "core/sw.js", content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response
