from decimal import Decimal

from django.utils.translation import gettext_lazy as _


def _budget_points(candidate, vacancy):
    rate = candidate.pricing_for(vacancy).final_rate
    max_rate = vacancy.max_rate_per_hour
    if max_rate * Decimal("0.9") <= rate <= max_rate:
        return 1
    else:
        return 0


def _remote_points(candidate, vacancy):
    gap = candidate.remote_days_per_week - vacancy.remote_days_allowed
    if gap == 0:
        return 1
    elif gap < 0:
        return 0.5
    else:
        return 0


def _hours_per_week_points(candidate, vacancy):
    if candidate.hours_per_week == vacancy.hours_per_week:
        return 1
    else:
        return 0


def _location_points(candidate, vacancy):
    if candidate.city and vacancy.city and candidate.city.strip().lower() == vacancy.city.strip().lower():
        return 1

    if candidate.travel_distance_km is None and candidate.city and vacancy.location:
        candidate.refresh_travel_distance()
        if candidate.travel_distance_km is not None and candidate.pk:
            type(candidate).objects.filter(pk=candidate.pk).update(travel_distance_km=candidate.travel_distance_km)

    if candidate.travel_distance_km is not None:
        return 1 if candidate.travel_distance_km <= 25 else 0

    return 0


# def _role_points(candidate, vacancy):
#     keywords = {k.strip().lower() for k in vacancy.skills.split(",") if k.strip()} | set(vacancy.title.lower().split())
#     text = f"{candidate.desired_role} {candidate.notes}".lower()
#     hits = sum(1 for k in keywords if k and k in text)
#     return min(WEIGHTS["role"], hits * 4)


PARTS = [
    ("budget", _("Budget fit"), _budget_points),
    ("remote", _("Remote days"), _remote_points),
    ("location", _("Location"), _location_points),
    ("hours_per_week", _("Hours per week"), _hours_per_week_points),
]

MAX_SCORE = len(PARTS)  # every part scores at most 1 point


def score(candidate, vacancy) -> dict:
    parts = [
        {"key": key, "label": label, "points": round(float(fn(candidate, vacancy)), 1)}
        for key, label, fn in PARTS
    ]
    return {"total": round(sum(p["points"] for p in parts), 1), "parts": parts}


def rank_candidates(vacancy, candidates):
    """Return [(candidate, score_dict), ...] best first."""
    scored = [(c, score(c, vacancy)) for c in candidates]
    return sorted(scored, key=lambda pair: pair[1]["total"], reverse=True)
