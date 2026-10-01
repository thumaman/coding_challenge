import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from clients.models import Vacancy

from . import constants as C
from .engine import PricingInput, calculate, rate_to_salary

INPUT_FIELDS = set(PricingInput.__dataclass_fields__)


def calculator(request):
    # TODO(Teun): polish the UI (proposed vs. max rate bar with the −10% band, prefill from ?candidate=<id>)
    vacancies = Vacancy.objects.filter(is_open=True).select_related("client")
    return render(request, "pricing/calculator.html", {"vacancies": vacancies, "defaults": C})


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


@require_POST
def calculate_api(request):
    """POST JSON with PricingInput fields -> PricingResult as JSON."""
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
    result = {k: (v if k == "breakdown" else str(v)) for k, v in result.items()}
    result["breakdown"] = [{**row, "value": str(row["value"])} for row in result["breakdown"]]
    return JsonResponse({"ok": True, "result": result})
