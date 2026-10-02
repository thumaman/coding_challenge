"""Pricing engine: the single source of truth for all rate calculations (owner: Teun).

Everything else (candidate list, calculator, matching, AI advisor) imports from here.
Never copy these formulas elsewhere, and never re-implement them in JavaScript.

Salary → tariff (candidate known):
    hourly      = monthly × 3 ÷ 13 ÷ hours_per_week
    cost        = hourly × cost_factor          (vacation days etc. are included in the factor)
    travel      = only when the travel distance is known AND the client doesn't pay travel itself
                  (otherwise it is left out of the breakdown entirely)
    tariff      = cost + travel + margin

Tariff → salary (indicative, before meeting a candidate, travel EXCLUDED):
    cost    = max_rate − margin
    hourly  = cost ÷ cost_factor
    monthly = hourly × hours_per_week × 13 ÷ 3

Calculations use unrounded Decimals; results are rounded to cents only on output.

`breakdown` is a list of groups; each group is a chain of rows with an operator
("", "+", "−", "×", "÷", "=") so the UI can show exactly which operation happens where.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.utils.translation import gettext as _

from . import constants as C
from . import travel as T
from .travel import estimate_monthly_travel_cost  # <-- IMPORTED NEW LOGIC

CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def D(value) -> Decimal:
    """Coerce floats/ints/strings/None to Decimal (None -> 0)."""
    if value is None or value == "":
        return Decimal(0)
    return value if isinstance(value, Decimal) else Decimal(str(value))


def num(value) -> str:
    """Plain number without trailing zeros or exponent: Decimal("40.00") -> "40" (not "4E+1")."""
    return format(D(value).normalize(), "f")


def _opt(value) -> Decimal | None:
    return None if value in (None, "") else D(value)


def row(op, label, value, kind="eur", detail=""):
    """kind: eur | hours | factor | text. `value` is the operand of `op`, rounded for display only."""
    if kind == "text":
        shown = value
    elif kind == "eur":
        shown = money(value)
    else:
        shown = num(D(value).quantize(Decimal("0.01")))
    return {"op": op, "label": label, "value": str(shown), "kind": kind, "detail": detail}


@dataclass
class PricingInput:
    salary_month: Decimal
    hours_per_week: Decimal = C.DEFAULT_HOURS_PER_WEEK
    cost_factor: Decimal = C.DEFAULT_COST_FACTOR
    margin: Decimal = C.DEFAULT_MARGIN
    # Travel only counts when the distance is known (business rule) and the client doesn't pay it
    travel_distance_km: Decimal | None = None  # one way
    transport_type: str = "car"  # car | ov | bicycle
    remote_days_per_week: Decimal = Decimal(0)  # days worked from home: no commute
    ov_subscription_month: Decimal | None = None  # <-- NEW: for fixed monthly OV costs
    client_pays_travel: bool = False
    # Use a fixed travel cost per hour instead of computing it from km (e.g. €2.13 in the brief)
    travel_per_hour_override: Decimal | None = None
    max_rate: Decimal | None = None  # client's maximum hourly rate (from the vacancy)
    proposed_rate: Decimal | None = None  # recruiter's chosen rate for a candidate (optional)

    def __post_init__(self):
        for name in ("salary_month", "hours_per_week", "cost_factor", "margin", "remote_days_per_week"):
            setattr(self, name, D(getattr(self, name)))
        for name in ("travel_distance_km", "travel_per_hour_override", "max_rate", "proposed_rate", "ov_subscription_month"):
            setattr(self, name, _opt(getattr(self, name)))
        self.client_pays_travel = self.client_pays_travel in (True, "true", "on", "1", 1)
        if self.hours_per_week <= 0:
            raise ValueError("hours_per_week must be positive")
        if self.remote_days_per_week < 0:
            raise ValueError("remote_days_per_week can't be negative")
        if self.cost_factor <= 0:
            raise ValueError("cost_factor must be positive")
        if not C.MIN_MARGIN <= self.margin <= C.MAX_MARGIN:
            raise ValueError(f"margin must be between {C.MIN_MARGIN} and {C.MAX_MARGIN}")

    @property
    def travel_known(self) -> bool:
        if self.travel_per_hour_override is not None:
            return True
        return self.travel_distance_km is not None


@dataclass
class PricingResult:
    hourly_wage: Decimal
    cost_price: Decimal
    travel_per_hour: Decimal  # what travel costs per hour (also when the client pays it)
    travel_in_tariff: Decimal  # the part included in the tariff
    travel_known: bool
    client_pays_travel: bool
    margin: Decimal
    advised_rate: Decimal
    final_rate: Decimal  # proposed_rate if set, else advised_rate
    max_rate: Decimal | None
    budget_status: str  # ok | too_low | over | unknown
    room_per_hour: Decimal | None  # max_rate − final_rate
    breakdown: list[dict] = field(default_factory=list)
    cost_steps: list[dict] = field(default_factory=list)  # compact salary → cost price chain (cost price dropdown)
    travel_steps: list[dict] = field(default_factory=list)  # how the travel costs / hour are built up (travel dropdown)

    def as_dict(self) -> dict:
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in self.__dict__.items()}


def hourly_from_monthly(salary_month, hours_per_week) -> Decimal:
    return D(salary_month) * C.MONTH_TO_WEEK / D(hours_per_week)


def monthly_from_hourly(hourly, hours_per_week) -> Decimal:
    return D(hourly) * D(hours_per_week) / C.MONTH_TO_WEEK


def workdays_per_week(hours_per_week) -> Decimal:
    return min(D(hours_per_week) / C.HOURS_PER_WORKDAY, Decimal(C.MAX_WORKDAYS_PER_WEEK))


def office_days_per_week(hours_per_week, remote_days_per_week=0) -> Decimal:
    """Days per week the candidate commutes: working days minus remote days."""
    return max(workdays_per_week(hours_per_week) - D(remote_days_per_week), Decimal(0))


def travel_cost_per_hour(distance_km, transport_type, hours_per_week, ov_subscription_month=0,
                         remote_days_per_week=0) -> Decimal:
    """Converts the static monthly travel allowance to an hourly cost."""
    office_days = office_days_per_week(hours_per_week, remote_days_per_week)

    monthly_cost = estimate_monthly_travel_cost(
        one_way_distance_km=distance_km or 0,
        days_worked_per_week=office_days,
        transport_method=transport_type,
        ov_subscription_cost=ov_subscription_month or 0
    )
    
    monthly_hours = D(hours_per_week) * Decimal("13") / Decimal("3")
    
    return D(monthly_cost) / monthly_hours


def budget_status(rate, max_rate) -> str:
    if max_rate is None or max_rate <= 0:
        return "unknown"
    if rate > max_rate:
        return "over"
    if rate < max_rate * (1 - C.TOO_LOW_THRESHOLD):
        return "too_low"
    return "ok"


def _travel_detail(inp: PricingInput) -> str:
    if inp.travel_per_hour_override is not None:
        return _("fixed amount")
    office_days = office_days_per_week(inp.hours_per_week, inp.remote_days_per_week)
    monthly_cost = estimate_monthly_travel_cost(
        inp.travel_distance_km or 0, office_days, inp.transport_type, inp.ov_subscription_month or 0
    )
    if inp.transport_type == "ov":
        return _("= €%(amount)s / mo (OV subscription)") % {"amount": num(monthly_cost)}
    return _("= €%(amount)s / mo (based on %(km)s km, %(days)s office days / week)") % {
        "amount": num(monthly_cost),
        "km": num(inp.travel_distance_km),
        "days": num(office_days.quantize(CENT)),
    }


def _travel_steps(inp: PricingInput, travel: Decimal) -> list[dict]:
    """Compact chain for the travel costs dropdown: only the essentials, ending in travel costs / hour."""
    if not inp.travel_known:
        return []
    if inp.travel_per_hour_override is not None:
        return [row("=", _("Travel costs / hour"), travel, detail=_("fixed amount"))]

    km = D(inp.travel_distance_km)
    office_days = office_days_per_week(inp.hours_per_week, inp.remote_days_per_week)

    if inp.transport_type == "ov":  # a monthly amount (subscription or capped flat rate)
        monthly = estimate_monthly_travel_cost(km, office_days, "ov", inp.ov_subscription_month or 0)
        return [
            row("", _("Travel costs / month"), monthly),
            row("÷", _("Hours / month"), num((D(inp.hours_per_week) * 13 / 3).quantize(CENT)), kind="hours"),
            row("=", _("Travel costs / hour"), travel),
        ]

    # Car / bicycle: tax-free allowance for every return trip on an office day.
    # Per hour = yearly cost ÷ hours per year (the same as monthly cost ÷ hours per month).
    days_per_year = T.WORKABLE_DAYS_PER_YEAR_FULL_TIME * office_days / T.FULL_TIME_DAYS_PER_WEEK
    remote = D(inp.remote_days_per_week)
    return [
        row("", _("Distance return trip"), f"{num(km * 2)} km", kind="text"),
        row("×", _("Office days / year"), num(days_per_year.quantize(CENT)), kind="text",
            detail=_("excl. %(days)s remote days / week") % {"days": num(remote)} if remote else ""),
        row("×", _("Tax-free rate / km"), T.TAX_FREE_RATE_PER_KM),
        row("÷", _("Hours / year"), num(D(inp.hours_per_week) * 52), kind="hours"),
        row("=", _("Travel costs / hour"), travel),
    ]


def calculate(inp: PricingInput) -> PricingResult:
    """Salary → tariff."""
    weekly = D(inp.salary_month) * C.MONTH_TO_WEEK
    hourly = weekly / inp.hours_per_week
    cost = hourly * inp.cost_factor

    if not inp.travel_known:
        travel = Decimal(0)
    elif inp.travel_per_hour_override is not None:
        travel = inp.travel_per_hour_override
    else:
        travel = travel_cost_per_hour(
            inp.travel_distance_km,
            inp.transport_type,
            inp.hours_per_week,
            inp.ov_subscription_month,
            inp.remote_days_per_week,
        )
        
    travel_in_tariff = Decimal(0) if inp.client_pays_travel else travel

    advised = cost + travel_in_tariff + inp.margin
    final = inp.proposed_rate if inp.proposed_rate is not None else advised
    status = budget_status(money(final), inp.max_rate)

    # Travel only appears in the tariff chain when it is actually charged (known and not paid by the client)
    tariff_rows = [row("", _("Cost price / hour"), cost)]
    if inp.travel_known and not inp.client_pays_travel:
        tariff_rows.append(row("+", _("Travel costs / hour"), travel, detail=_travel_detail(inp)))
    tariff_rows += [row("+", _("Margin / hour"), inp.margin), row("=", _("Advised tariff / hour"), advised)]

    breakdown = [
        {"title": _("Gross hourly wage"), "rows": [
            row("", _("Gross salary / month"), inp.salary_month),
            row("×", _("Month → week"), "3 ÷ 13", kind="text",
                detail=_("= €%(amount)s / week") % {"amount": money(weekly)}),
            row("÷", _("Hours per week"), inp.hours_per_week, kind="hours"),
            row("=", _("Gross hourly wage"), hourly),
        ]},
        {"title": _("Cost price"), "rows": [
            row("", _("Gross hourly wage"), hourly),
            row("×", _("Cost price factor"), inp.cost_factor, kind="factor",
                detail=_("includes vacation days and other employment conditions")),
            row("=", _("Cost price / hour"), cost),
        ]},
        {"title": _("Advised tariff"), "rows": tariff_rows},
    ]

    cost_steps = [
        row("", _("Gross salary / month"), inp.salary_month),
        row("=", _("Hourly wage"), hourly,
            detail=_("× 3 ÷ 13 ÷ %(hours)s h") % {"hours": num(inp.hours_per_week)}),
        row("×", _("Cost price factor"), inp.cost_factor, kind="factor"),
        row("=", _("Cost price / hour"), cost),
    ]

    return PricingResult(
        hourly_wage=money(hourly),
        cost_price=money(cost),
        travel_per_hour=money(travel),
        travel_in_tariff=money(travel_in_tariff),
        travel_known=inp.travel_known,
        client_pays_travel=inp.client_pays_travel,
        margin=money(inp.margin),
        advised_rate=money(advised),
        final_rate=money(final),
        max_rate=inp.max_rate,
        budget_status=status,
        room_per_hour=money(inp.max_rate - final) if inp.max_rate is not None else None,
        breakdown=breakdown,
        cost_steps=cost_steps,
        travel_steps=_travel_steps(inp, travel),
    )


def rate_to_salary(max_rate, margin=C.DEFAULT_MARGIN, cost_factor=C.DEFAULT_COST_FACTOR,
                   hours_per_week=C.DEFAULT_HOURS_PER_WEEK) -> dict:
    """Tariff → salary: indicative max gross monthly salary. Travel is deliberately excluded."""
    max_rate, margin, cost_factor, hours = D(max_rate), D(margin), D(cost_factor), D(hours_per_week)
    cost = max_rate - margin
    hourly = cost / cost_factor
    weekly = hourly * hours
    monthly = monthly_from_hourly(hourly, hours)
    return {
        "cost_price": money(cost),
        "hourly_wage": money(hourly),
        "weekly_salary": money(weekly),
        "monthly_salary": money(monthly),
        # Compact chain for the salary dropdown
        "steps": [
            row("", _("Client tariff / hour"), max_rate),
            row("−", _("Margin / hour"), margin),
            row("=", _("Cost price / hour"), cost),
            row("÷", _("Cost price factor"), cost_factor, kind="factor"),
            row("=", _("Hourly wage"), hourly),
            row("=", _("Max gross salary / month"), monthly,
                detail=_("× %(hours)s h × 13 ÷ 3") % {"hours": num(hours)}),
        ],
        "breakdown": [
            {"title": _("Cost price"), "rows": [
                row("", _("Client tariff / hour"), max_rate),
                row("−", _("Margin / hour"), margin),
                row("=", _("Cost price / hour"), cost),
            ]},
            {"title": _("Gross hourly wage"), "rows": [
                row("", _("Cost price / hour"), cost),
                row("÷", _("Cost price factor"), cost_factor, kind="factor"),
                row("=", _("Gross hourly wage"), hourly),
            ]},
            {"title": _("Gross salary / month"), "rows": [
                row("", _("Gross hourly wage"), hourly),
                row("×", _("Hours per week"), hours, kind="hours", detail=_("= €%(amount)s / week") % {"amount": money(weekly)}),
                row("×", _("Week → month"), "13 ÷ 3", kind="text"),
                row("=", _("Max gross salary / month"), monthly, detail=_("excl. travel costs")),
            ]},
        ],
    }