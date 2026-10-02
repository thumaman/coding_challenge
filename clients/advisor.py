"""Advisor: proposes tweaks when a candidate is over the client's budget (owner: Ivan).

A deterministic solver (always works) uses pricing.engine to find the change per lever that
brings the rate within max_rate_per_hour, plus a combined option. 
Options are ranked purely by least intervention (rule-based).

Each option: {"key", "title", "changes": {field: value}, "new_rate", "savings_per_hour", "reason"}
`changes` keys are Candidate model fields, so clients:apply_tweak can apply them directly.
"""

from __future__ import annotations

import json
from decimal import ROUND_DOWN, Decimal

from django.utils.translation import gettext as _

from pricing.engine import C, calculate, money

# The advisor never suggests a margin below this, even though recruiters may go lower by hand
MARGIN_FLOOR = Decimal("5.00")


def _rate(candidate, vacancy, **overrides) -> Decimal:
    inp = candidate.pricing_input(vacancy=vacancy, proposed_rate=None, **overrides)
    return calculate(inp).advised_rate


def _option(candidate, vacancy, key, title, changes, current, reason):
    """`changes` uses PricingInput names; they are stored as Candidate model fields."""
    model_changes = {candidate.PRICING_FIELD_MAP.get(k, k): v for k, v in changes.items()}
    new_rate = _rate(candidate, vacancy, **changes)
    serialized = {k: str(v) for k, v in model_changes.items()}
    return {
        "key": key,
        "title": title,
        "changes": serialized,
        "changes_json": json.dumps(serialized),
        "new_rate": str(new_rate),
        "savings_per_hour": str(money(current - new_rate)),
        "fits": new_rate <= vacancy.max_rate_per_hour,
        "reason": reason,
    }


def _solve_salary(candidate, vacancy, max_rate, **fixed) -> Decimal:
    """Highest monthly salary (rounded down to €10) that fits, with other inputs fixed."""
    inp = candidate.pricing_input(vacancy=vacancy, proposed_rate=None, **fixed)
    result = calculate(inp)
    headroom = max_rate - inp.margin - result.travel_in_tariff
    hourly = headroom / inp.cost_factor
    salary = hourly * inp.hours_per_week / C.MONTH_TO_WEEK
    return (salary / 10).quantize(Decimal(1), rounding=ROUND_DOWN) * 10


def suggest_tweaks(candidate, vacancy=None) -> list[dict]:
    vacancy = vacancy or candidate.vacancy
    if vacancy is None:
        return []
        
    max_rate = vacancy.max_rate_per_hour
    current = _rate(candidate, vacancy)
    
    # ---------------------------------------------------------------------
    # NEW: Suggestion when the price is much lower than the client's budget
    # ---------------------------------------------------------------------
    # E.g., If current rate is more than 10% below the client's max budget
    if current < (max_rate * Decimal("0.9")):
        return [{
            "key": "increase_margin",
            "title": _("Increase Margin or Salary"),
            "changes": {},
            "changes_json": "{}",
            "new_rate": str(current),
            "savings_per_hour": "0.00",
            "fits": True,
            "reason": _("Advised price is significantly lower than the client offer; consider increasing the margin or the candidate's salary."),
        }]
        
    # If the price is perfectly fine, suggest nothing
    if current <= max_rate:
        return []
        
    pricing = calculate(candidate.pricing_input(vacancy=vacancy, proposed_rate=None))
    options = []

    # Lever 1: salary
    salary = _solve_salary(candidate, vacancy, max_rate)
    if salary > 0:
        options.append(_option(candidate, vacancy, "salary", _("Lower salary"),
                               {"salary_month": salary}, current,
                               _("Gross salary to €%(salary)s/month brings the tariff within €%(max)s.")
                               % {"salary": salary, "max": max_rate}))

    # Lever 2: margin (down to the minimum)
    needed_margin = candidate.margin_per_hour - (current - max_rate)
    if needed_margin >= MARGIN_FLOOR:
        margin = needed_margin.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        options.append(_option(candidate, vacancy, "margin", _("Lower margin"),
                               {"margin": margin}, current,
                               _("Reduce our margin to €%(margin)s/hour; the candidate's terms stay the same.")
                               % {"margin": margin}))

    # Lever 3: the client pays the travel costs
    if pricing.travel_in_tariff > 0:
        options.append(_option(candidate, vacancy, "client_travel", _("Client pays travel costs"),
                               {"client_pays_travel": True}, current,
                               _("Ask %(client)s to reimburse travel costs (€%(travel)s/hour) separately.")
                               % {"client": vacancy.client.name, "travel": pricing.travel_in_tariff}))

    # Lever 4: cheaper travel means
    if pricing.travel_in_tariff > 0:
        for transport, label in candidate.Transport.choices:
            if transport != candidate.transport_type and _rate(candidate, vacancy, transport_type=transport) < current:
                options.append(_option(candidate, vacancy, "transport", _("Travel by %(means)s") % {"means": label.lower()},
                                       {"transport_type": transport}, current,
                                       _("Cheaper travel means lowers the travel costs.")))

    # Combined: margin to the minimum, then the smallest salary change on top
    combined_salary = _solve_salary(candidate, vacancy, max_rate, margin=MARGIN_FLOOR)
    if 0 < combined_salary < candidate.expected_salary_month:
        options.append(_option(candidate, vacancy, "combined", _("Split the difference"),
                               {"margin": MARGIN_FLOOR, "salary_month": combined_salary}, current,
                               _("Margin to €%(margin)s and salary to €%(salary)s/month: both sides give a little.")
                               % {"margin": MARGIN_FLOOR, "salary": combined_salary}))

    options = [o for o in options if o["fits"]]
    
    # Rule-based ranking: smallest change to the candidate's package first
    preference = {"client_travel": 0, "margin": 1, "transport": 2, "combined": 3, "salary": 4}
    options.sort(key=lambda o: preference.get(o["key"], 9))
    
    return options