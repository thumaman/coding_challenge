"""Advisor: proposes tweaks when a candidate is over the client's budget (owner: Ivan).

A deterministic solver (always works) uses pricing.engine to find the change per lever that
brings the rate within max_rate_per_hour, plus a combined option. 
Options are ranked purely by least intervention (rule-based).

Advice is per CandidateVacancy (a candidate at one vacancy): each vacancy has its own budget and travel.
Each option: {"key", "title", "changes": {field: value}, "new_rate", "savings_per_hour", "reason"}
`changes` keys are Candidate or CandidateVacancy model fields.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from django.utils.translation import gettext as _

from pricing.engine import C, calculate, money

# The advisor never suggests a margin below this, even though recruiters may go lower by hand
MARGIN_FLOOR = Decimal("5.00")


def _input(link, **overrides):
    return link.candidate.pricing_input(link=link, proposed_rate=None, **overrides)


def _rate(link, **overrides) -> Decimal:
    return calculate(_input(link, **overrides)).advised_rate


def _option(link, key, title, changes, current, reason):
    """`changes` uses PricingInput names; they are stored as Candidate / CandidateVacancy model fields."""
    field_map = {**link.candidate.PRICING_FIELD_MAP, **link.candidate.LINK_PRICING_FIELD_MAP}
    model_changes = {field_map.get(k, k): v for k, v in changes.items()}
    new_rate = _rate(link, **changes)
    serialized = {k: str(v) for k, v in model_changes.items()}
    return {
        "key": key,
        "title": title,
        "changes": serialized,
        "new_rate": str(new_rate),
        "savings_per_hour": str(money(current - new_rate)),
        "fits": new_rate <= link.vacancy.max_rate_per_hour,
        "reason": reason,
    }


def _solve_salary(link, max_rate, **fixed) -> Decimal:
    """Highest monthly salary (rounded down to €10) that fits, with other inputs fixed."""
    inp = _input(link, **fixed)
    result = calculate(inp)
    headroom = max_rate - inp.margin - result.travel_in_tariff
    hourly = headroom / inp.cost_factor
    salary = hourly * inp.hours_per_week / C.MONTH_TO_WEEK
    return (salary / 10).quantize(Decimal(1), rounding=ROUND_DOWN) * 10


def suggest_tweaks(link) -> list[dict]:
    """Options that bring `link` (a CandidateVacancy) within its vacancy's maximum rate, or a hint to raise
    margin/salary when the rate is well below it."""
    candidate, vacancy = link.candidate, link.vacancy
    max_rate = vacancy.max_rate_per_hour
    current = _rate(link)

    # More than 10% below the client's maximum: there is room to earn (or pay) more
    if current < max_rate * Decimal("0.9"):
        return [{
            "key": "increase_margin",
            "title": _("Increase Margin or Salary"),
            "changes": {},
            "new_rate": str(current),
            "savings_per_hour": "0.00",
            "fits": True,
            "reason": _("Advised price is significantly lower than the client offer; consider increasing the margin or the candidate's salary."),
        }]
    if current <= max_rate:
        return []
    pricing = calculate(_input(link))

    options = []

    # Lever 1: salary
    salary = _solve_salary(link, max_rate)
    if salary > 0:
        options.append(_option(link, "salary", _("Lower salary"),
                               {"salary_month": salary}, current,
                               _("Gross salary to €%(salary)s/month brings the tariff within €%(max)s.")
                               % {"salary": salary, "max": max_rate}))

    # Lever 2: margin (down to the minimum)
    needed_margin = candidate.margin_per_hour - (current - max_rate)
    if needed_margin >= MARGIN_FLOOR:
        margin = needed_margin.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        options.append(_option(link, "margin", _("Lower margin"),
                               {"margin": margin}, current,
                               _("Reduce our margin to €%(margin)s/hour; the candidate's terms stay the same.")
                               % {"margin": margin}))

    # Lever 3: the client pays the travel costs
    if pricing.travel_in_tariff > 0:
        options.append(_option(link, "client_travel", _("Client pays travel costs"),
                               {"client_pays_travel": True}, current,
                               _("Ask %(client)s to reimburse travel costs (€%(travel)s/hour) separately.")
                               % {"client": vacancy.client.name, "travel": pricing.travel_in_tariff}))

    # Lever 4: cheaper travel means
    if pricing.travel_in_tariff > 0:
        for transport, label in candidate.Transport.choices:
            if transport != candidate.transport_type and _rate(link, transport_type=transport) < current:
                options.append(_option(link, "transport", _("Travel by %(means)s") % {"means": label.lower()},
                                       {"transport_type": transport}, current,
                                       _("Cheaper travel means lowers the travel costs.")))

    # Combined: margin to the minimum, then the smallest salary change on top
    combined_salary = _solve_salary(link, max_rate, margin=MARGIN_FLOOR)
    if 0 < combined_salary < candidate.expected_salary_month:
        options.append(_option(link, "combined", _("Split the difference"),
                               {"margin": MARGIN_FLOOR, "salary_month": combined_salary}, current,
                               _("Margin to €%(margin)s and salary to €%(salary)s/month: both sides give a little.")
                               % {"margin": MARGIN_FLOOR, "salary": combined_salary}))

    options = [o for o in options if o["fits"]]
    
    # Rule-based ranking: smallest change to the candidate's package first
    preference = {"client_travel": 0, "margin": 1, "transport": 2, "combined": 3, "salary": 4}
    options.sort(key=lambda o: preference.get(o["key"], 9))
    
    return options