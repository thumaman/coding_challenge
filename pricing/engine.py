"""Pricing engine: the single source of truth for all rate calculations (owner: Teun).

Everything else (candidate list, calculator, matching, AI advisor) imports from here.
Never copy these formulas elsewhere, and never re-implement them in JavaScript.

Salary → rate (candidate known):
    hourly      = monthly × 3 ÷ 13 ÷ hours_per_week
    cost        = hourly × cost_factor
    all_in_cost = cost + travel_per_hour   (only when travel data is known!)
    rate        = all_in_cost + margin

Rate → salary (indicative, before meeting a candidate, travel EXCLUDED):
    cost    = max_rate − margin
    hourly  = cost ÷ cost_factor
    monthly = hourly × hours_per_week × 13 ÷ 3

Calculations use unrounded Decimals; results are rounded to cents only on output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from . import constants as C

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def D(value) -> Decimal:
    """Coerce floats/ints/strings/None to Decimal (None -> 0)."""
    if value is None or value == "":
        return Decimal(0)
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass
class PricingInput:
    salary_month: Decimal
    hours_per_week: Decimal = C.DEFAULT_HOURS_PER_WEEK
    cost_factor: Decimal = C.DEFAULT_COST_FACTOR
    margin: Decimal = C.DEFAULT_MARGIN
    # Travel only counts when the candidate's travel data is known (business rule)
    travel_known: bool = False
    travel_distance_km: Decimal = Decimal(0)  # one way
    transport_type: str = "none"  # car | ov | bike | none
    remote_days: int = 0
    # Use a fixed travel cost per hour instead of computing it from km (e.g. €2.13 in the brief)
    travel_per_hour_override: Decimal | None = None
    vacation_days: int = C.REFERENCE_VACATION_DAYS
    sick_days: int = C.REFERENCE_SICK_DAYS
    benefits_month: Decimal = Decimal(0)  # secondary benefits in € per month
    max_rate: Decimal | None = None  # client's maximum hourly rate (from the vacancy)
    proposed_rate: Decimal | None = None  # recruiter's manual override

    def __post_init__(self):
        for name in ("salary_month", "hours_per_week", "cost_factor", "margin", "travel_distance_km", "benefits_month"):
            setattr(self, name, D(getattr(self, name)))
        for name in ("max_rate", "proposed_rate", "travel_per_hour_override"):
            value = getattr(self, name)
            setattr(self, name, None if value in (None, "") else D(value))
        self.remote_days = int(self.remote_days or 0)
        self.vacation_days = int(self.vacation_days if self.vacation_days is not None else C.REFERENCE_VACATION_DAYS)
        self.sick_days = int(self.sick_days if self.sick_days is not None else C.REFERENCE_SICK_DAYS)
        if self.hours_per_week <= 0:
            raise ValueError("hours_per_week must be positive")


@dataclass
class PricingResult:
    hourly_wage: Decimal
    effective_factor: Decimal
    cost_price: Decimal
    benefits_per_hour: Decimal
    travel_per_hour: Decimal
    all_in_cost: Decimal
    margin: Decimal
    advised_rate: Decimal
    final_rate: Decimal  # proposed_rate if set, else advised_rate
    max_rate: Decimal | None
    budget_status: str  # ok | too_low | over | unknown
    room_per_hour: Decimal | None  # max_rate − final_rate
    breakdown: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        data = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in self.__dict__.items()}
        data["breakdown"] = [{**row, "value": str(row["value"])} for row in self.breakdown]
        return data


def hourly_from_monthly(salary_month, hours_per_week) -> Decimal:
    return D(salary_month) * C.MONTH_TO_WEEK / D(hours_per_week)


def monthly_from_hourly(hourly, hours_per_week) -> Decimal:
    return D(hourly) * D(hours_per_week) / C.MONTH_TO_WEEK


def per_hour_from_monthly(amount_month, hours_per_week) -> Decimal:
    return D(amount_month) * C.MONTH_TO_WEEK / D(hours_per_week)


def travel_cost_per_hour(distance_km, transport_type, remote_days, hours_per_week) -> Decimal:
    """ASSUMPTION: km_one_way × 2 × office_days × €/km ÷ hours_per_week.

    office_days = workdays (hours ÷ 8, max 5) − remote days.
    TODO(Teun): validate with the client (public transport passes, fixed allowances).
    """
    rate = C.TRAVEL_RATE_PER_KM.get(transport_type, Decimal(0))
    workdays = min(D(hours_per_week) / C.HOURS_PER_WORKDAY, Decimal(C.MAX_WORKDAYS_PER_WEEK))
    office_days = max(workdays - D(remote_days), Decimal(0))
    return D(distance_km) * 2 * office_days * rate / D(hours_per_week)


def effective_factor(base_factor, vacation_days, sick_days) -> Decimal:
    """ASSUMPTION: scale the cost factor by productive days vs. the reference situation.

    With the reference values (25 vacation, 8 sick days) the factor is unchanged.
    TODO(Teun): validate with the client.
    """
    def productive(vacation, sick):
        return C.WORKDAYS_PER_YEAR - C.PUBLIC_HOLIDAYS - vacation - sick

    reference = productive(C.REFERENCE_VACATION_DAYS, C.REFERENCE_SICK_DAYS)
    actual = max(productive(vacation_days, sick_days), 1)
    return D(base_factor) * Decimal(reference) / Decimal(actual)


def budget_status(rate, max_rate) -> str:
    if max_rate is None or max_rate <= 0:
        return "unknown"
    if rate > max_rate:
        return "over"
    if rate < max_rate * (1 - C.TOO_LOW_THRESHOLD):
        return "too_low"
    return "ok"


def calculate(inp: PricingInput) -> PricingResult:
    """Salary → rate."""
    hourly = hourly_from_monthly(inp.salary_month, inp.hours_per_week)
    factor = effective_factor(inp.cost_factor, inp.vacation_days, inp.sick_days)
    cost = hourly * factor
    benefits = per_hour_from_monthly(inp.benefits_month, inp.hours_per_week)

    if not inp.travel_known:
        travel = Decimal(0)
    elif inp.travel_per_hour_override is not None:
        travel = inp.travel_per_hour_override
    else:
        travel = travel_cost_per_hour(inp.travel_distance_km, inp.transport_type, inp.remote_days, inp.hours_per_week)

    all_in = cost + benefits + travel
    advised = all_in + inp.margin
    final = inp.proposed_rate if inp.proposed_rate is not None else advised
    status = budget_status(money(final), inp.max_rate)

    breakdown = [
        {"key": "hourly", "label": "Gross hourly wage", "formula": f"€{money(inp.salary_month)} × 3 ÷ 13 ÷ {inp.hours_per_week}h", "value": money(hourly)},
        {"key": "cost", "label": "Cost price", "formula": f"× factor {factor.quantize(Decimal('0.001'))}", "value": money(cost)},
    ]
    if benefits:
        breakdown.append({"key": "benefits", "label": "Secondary benefits", "formula": f"€{money(inp.benefits_month)}/month", "value": money(benefits)})
    breakdown += [
        {"key": "travel", "label": "Travel costs", "formula": "per hour" if inp.travel_known else "not known yet, excluded", "value": money(travel)},
        {"key": "all_in", "label": "All-in cost price", "formula": "", "value": money(all_in)},
        {"key": "margin", "label": "Margin", "formula": "per hour", "value": money(inp.margin)},
        {"key": "advised", "label": "Advised rate", "formula": "", "value": money(advised)},
    ]

    return PricingResult(
        hourly_wage=money(hourly),
        effective_factor=factor,
        cost_price=money(cost),
        benefits_per_hour=money(benefits),
        travel_per_hour=money(travel),
        all_in_cost=money(all_in),
        margin=money(inp.margin),
        advised_rate=money(advised),
        final_rate=money(final),
        max_rate=inp.max_rate,
        budget_status=status,
        room_per_hour=money(inp.max_rate - final) if inp.max_rate is not None else None,
        breakdown=breakdown,
    )


def rate_to_salary(max_rate, margin=C.DEFAULT_MARGIN, cost_factor=C.DEFAULT_COST_FACTOR,
                   hours_per_week=C.DEFAULT_HOURS_PER_WEEK) -> dict:
    """Rate → salary: indicative max gross monthly salary. Travel is deliberately excluded."""
    cost = D(max_rate) - D(margin)
    hourly = cost / D(cost_factor)
    weekly = hourly * D(hours_per_week)
    monthly = monthly_from_hourly(hourly, hours_per_week)
    return {
        "cost_price": money(cost),
        "hourly_wage": money(hourly),
        "weekly_salary": money(weekly),
        "monthly_salary": money(monthly),
        "breakdown": [
            {"key": "cost", "label": "Cost price", "formula": f"€{money(max_rate)} − €{money(margin)} margin", "value": money(cost)},
            {"key": "hourly", "label": "Gross hourly wage", "formula": f"÷ factor {D(cost_factor)}", "value": money(hourly)},
            {"key": "weekly", "label": "Gross weekly salary", "formula": f"× {D(hours_per_week)}h", "value": money(weekly)},
            {"key": "monthly", "label": "Indicative max monthly salary", "formula": "× 13 ÷ 3 (excl. travel costs)", "value": money(monthly)},
        ],
    }
