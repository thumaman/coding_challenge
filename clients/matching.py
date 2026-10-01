"""Candidate ↔ vacancy matching score (owner: Ivan).

score(candidate, vacancy) -> {"total": 0-100, "parts": [{"key", "label", "points", "max"}...]}

v1 weights: budget fit 40, salary range 20, remote 15, location 15, role keywords 10.
TODO(Ivan): tune weights, use real distance instead of city equality, smarter keyword matching.
"""

from decimal import Decimal

WEIGHTS = {"budget": 40, "salary": 20, "remote": 15, "location": 15, "role": 10}


def _budget_points(candidate, vacancy):
    rate = candidate.pricing_for(vacancy).final_rate
    max_rate = vacancy.max_rate_per_hour
    if rate <= max_rate:
        # Full points within budget; small penalty when far below (risk of "too cheap")
        return WEIGHTS["budget"] if rate >= max_rate * Decimal("0.9") else WEIGHTS["budget"] * 0.8
    over = (rate - max_rate) / max_rate  # e.g. 0.1 = 10% over budget
    return max(0.0, WEIGHTS["budget"] * (1 - float(over) * 4))


def _salary_points(candidate, vacancy):
    salary = candidate.expected_salary_month
    if vacancy.min_salary and salary < vacancy.min_salary:
        return WEIGHTS["salary"] * 0.7
    if vacancy.max_salary and salary > vacancy.max_salary:
        over = float((salary - vacancy.max_salary) / vacancy.max_salary)
        return max(0.0, WEIGHTS["salary"] * (1 - over * 3))
    return WEIGHTS["salary"]


def _remote_points(candidate, vacancy):
    gap = candidate.remote_days_per_week - vacancy.remote_days_allowed
    return WEIGHTS["remote"] if gap <= 0 else max(0, WEIGHTS["remote"] - gap * 5)


def _location_points(candidate, vacancy):
    if candidate.city and vacancy.city and candidate.city.strip().lower() == vacancy.city.strip().lower():
        return WEIGHTS["location"]
    if candidate.travel_known and candidate.travel_distance_km is not None:
        return max(0, WEIGHTS["location"] - float(candidate.travel_distance_km) / 10)
    return WEIGHTS["location"] / 2


def _role_points(candidate, vacancy):
    keywords = {k.strip().lower() for k in vacancy.skills.split(",") if k.strip()} | set(vacancy.title.lower().split())
    text = f"{candidate.desired_role} {candidate.notes}".lower()
    hits = sum(1 for k in keywords if k and k in text)
    return min(WEIGHTS["role"], hits * 4)


PARTS = [
    ("budget", "Budget fit", _budget_points),
    ("salary", "Salary in range", _salary_points),
    ("remote", "Remote days", _remote_points),
    ("location", "Location", _location_points),
    ("role", "Role / skills", _role_points),
]


def score(candidate, vacancy) -> dict:
    parts = [
        {"key": key, "label": label, "points": round(float(fn(candidate, vacancy)), 1), "max": WEIGHTS[key]}
        for key, label, fn in PARTS
    ]
    return {"total": round(sum(p["points"] for p in parts)), "parts": parts}


def rank_candidates(vacancy, candidates):
    """Return [(candidate, score_dict), ...] best first."""
    scored = [(c, score(c, vacancy)) for c in candidates]
    return sorted(scored, key=lambda pair: pair[1]["total"], reverse=True)
