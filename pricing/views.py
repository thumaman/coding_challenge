import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from candidates.models import Candidate
from clients.models import Vacancy

from . import constants as C
from .engine import PricingInput, calculate, rate_to_salary
from .travel import route_distance_km

INPUT_FIELDS = set(PricingInput.__dataclass_fields__)


def _initial_from_candidate(candidate_id):
    candidate = Candidate.objects.select_related("vacancy").filter(pk=candidate_id).first()
    if not candidate:
        return {}
    return {
        "candidate": candidate,
        "vacancy_id": candidate.vacancy_id,
        "client_pays_travel": bool(candidate.vacancy and candidate.vacancy.client_pays_travel),
        "salary_month": candidate.expected_salary_month,
        "hours_per_week": candidate.hours_per_week,
        "home_location": candidate.city,
        "transport_type": candidate.transport_type,
        "travel_distance_km": candidate.travel_distance_km,
        "cost_factor": candidate.cost_factor,
        "margin": candidate.margin_per_hour,
    }


def calculator(request):
    # TODO(Teun): proposed vs. max tariff bar with the −10% band
    vacancies = Vacancy.objects.filter(is_open=True).select_related("client")
    initial = _initial_from_candidate(request.GET.get("candidate")) if request.GET.get("candidate") else {}
    i18n = {
        "status": {
            "ok": _("Within the client's budget"),
            "too_low": _("More than 10% below the client's maximum: too cheap?"),
            "over": _("Over the client's budget"),
            "unknown": _("Choose a vacancy to compare with the client's budget"),
        },
        "room": _("Room: %(amount)s / hour"),
        "distance_loading": _("Calculating distance…"),
        "distance_route": _("Route distance from %(from)s to %(to)s."),
        "distance_estimate": _("Estimated distance (route service unavailable)."),
        "distance_failed": _("Location not found: enter the distance yourself."),
        "distance_needed": _("Choose a vacancy and enter the home location to calculate the distance."),
    }
    return render(request, "pricing/calculator.html", {"vacancies": vacancies, "C": C, "i18n": i18n, "initial": initial})


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


@require_POST
def calculate_api(request):
    """POST JSON with PricingInput fields (+ optional vacancy_id) -> PricingResult as JSON."""
    data = _payload(request)
    if data is None:
        return JsonResponse({"ok": False, "message": "Invalid JSON"}, status=400)
    if data.get("vacancy_id") and not data.get("max_rate"):
        vacancy = Vacancy.objects.filter(pk=data["vacancy_id"]).first()
        data["max_rate"] = vacancy.max_rate_per_hour if vacancy else None
    try:
        result = calculate(PricingInput(**{k: v for k, v in data.items() if k in INPUT_FIELDS}))
    except (TypeError, ValueError, ArithmeticError) as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    return JsonResponse({"ok": True, "result": result.as_dict()})


@require_POST
def reverse_api(request):
    """POST {max_rate, margin, cost_factor, hours_per_week} -> indicative max monthly salary."""
    data = _payload(request)
    if data is None or not data.get("max_rate"):
        return JsonResponse({"ok": False, "message": "max_rate is required"}, status=400)
    try:
        result = rate_to_salary(
            data["max_rate"],
            data.get("margin", C.DEFAULT_MARGIN),
            data.get("cost_factor", C.DEFAULT_COST_FACTOR),
            data.get("hours_per_week", C.DEFAULT_HOURS_PER_WEEK),
        )
    except (TypeError, ValueError, ArithmeticError) as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    return JsonResponse({"ok": True, "result": {k: (v if k == "breakdown" else str(v)) for k, v in result.items()}})


@require_GET
def distance_api(request):
    """GET ?origin=<candidate home>&destination=<work location> -> one-way distance in km."""
    origin, destination = request.GET.get("origin", ""), request.GET.get("destination", "")
    if not origin.strip() or not destination.strip():
        return JsonResponse({"ok": False, "message": _("Enter both locations.")}, status=400)
    result = route_distance_km(origin, destination)
    if result is None:
        return JsonResponse({"ok": False, "message": _("Location not found.")}, status=404)
    return JsonResponse({"ok": True, "km": str(result["km"]), "source": result["source"]})
