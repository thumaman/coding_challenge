"""AI advisor: proposes tweaks when a candidate is over the client's budget (owner: Ivan).

1. A deterministic solver (always works) uses pricing.engine to find the change per lever that
   brings the rate within max_rate_per_hour, plus a combined option.
2. Optional: when ANTHROPIC_API_KEY is set, Claude ranks the options and explains them in
   recruiter-friendly language. Any failure falls back to the rule-based ranking, so the demo never breaks.

Each option: {"key", "title", "changes": {field: value}, "new_rate", "savings_per_hour", "reason"}
`changes` keys are Candidate model fields, so clients:apply_tweak can apply them directly.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import ROUND_DOWN, Decimal

from django.conf import settings
from django.utils.translation import gettext as _

from pricing.engine import C, calculate, money

logger = logging.getLogger(__name__)

# The advisor never suggests a margin below this, even though recruiters may go lower by hand
MARGIN_FLOOR = Decimal("5.00")


def _rate(candidate, vacancy, client_pays_travel=None, **overrides) -> Decimal:
    if client_pays_travel is not None:
        overrides["client_pays_travel"] = client_pays_travel
    inp = candidate.pricing_input(vacancy=vacancy, proposed_rate=None, **overrides)
    return calculate(inp).advised_rate


def _option(candidate, vacancy, key, title, changes, current, reason):
    """`changes` uses PricingInput names; `vacancy.<field>` keys change the vacancy instead."""
    model_changes = {
        (k if k.startswith("vacancy.") else candidate.PRICING_FIELD_MAP.get(k, k)): v for k, v in changes.items()
    }
    rate_changes = {k.removeprefix("vacancy."): v for k, v in changes.items()}
    new_rate = _rate(candidate, vacancy, **rate_changes)
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

    # Lever 3: the client pays the travel costs (changes the vacancy)
    if pricing.travel_in_tariff > 0:
        options.append(_option(candidate, vacancy, "client_travel", _("Client pays travel costs"),
                               {"vacancy.client_pays_travel": True}, current,
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
    return _rank_with_claude(candidate, vacancy, options) if options else options


def _rank_with_claude(candidate, vacancy, options):
    """Optional AI layer. Returns options re-ordered with an `ai_explanation` each, or unchanged on any error."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return options
    try:
        import anthropic
        from pydantic import BaseModel

        class RankedOption(BaseModel):
            key: str
            explanation: str

        class Ranking(BaseModel):
            options: list[RankedOption]

        prompt = (
            "You advise a recruiter during an intake conversation. The candidate's advised hourly rate is "
            f"above the client's maximum of €{vacancy.max_rate_per_hour}. Rank these tweak options from most to "
            "least acceptable for both the candidate and the recruitment agency, and give each a 1-2 sentence "
            "explanation the recruiter can say out loud. Use the option keys as given.\n\n"
            f"Candidate role: {candidate.desired_role}\n"
            f"Candidate notes (what they care about): {candidate.notes or '-'}\n"
            f"Options: {[{k: o[k] for k in ('key', 'title', 'changes', 'new_rate', 'reason')} for o in options]}"
        )
        client = anthropic.Anthropic(timeout=20.0)
        response = client.messages.parse(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            output_format=Ranking,
        )
        ranking = response.parsed_output
        if ranking is None:
            return options
        by_key = {o["key"]: o for o in options}
        ranked = []
        for item in ranking.options:
            if item.key in by_key:
                ranked.append({**by_key.pop(item.key), "ai_explanation": item.explanation})
        return ranked + list(by_key.values())
    except Exception:  # noqa: BLE001 - the demo must never break on the AI layer
        logger.exception("Claude ranking failed, falling back to rule-based ranking")
        return options
