"""Pricing defaults and assumptions (owner: Teun).

Values marked ASSUMPTION are our own interpretation and must be validated with the client.
"""

from decimal import Decimal

DEFAULT_COST_FACTOR = Decimal("2.0")      # "kostprijsfactor": total employer cost ≈ 2× gross wage
DEFAULT_MARGIN = Decimal("10.00")         # € per hour on top of the all-in cost price
DEFAULT_HOURS_PER_WEEK = Decimal("40")

# Monthly ↔ weekly conversion used by the client: weekly = monthly × 3 ÷ 13
MONTH_TO_WEEK = Decimal(3) / Decimal(13)

# Warning when the proposed rate is more than this fraction BELOW the client's max rate
# ("candidates get rejected for being too cheap").
TOO_LOW_THRESHOLD = Decimal("0.10")

# ASSUMPTION: travel cost per km (return trip is counted), by transport type
TRAVEL_RATE_PER_KM = {
    "car": Decimal("0.23"),
    "ov": Decimal("0.20"),
    "bike": Decimal("0"),
    "none": Decimal("0"),
}
HOURS_PER_WORKDAY = Decimal("8")
MAX_WORKDAYS_PER_WEEK = 5

# ASSUMPTION: vacation/sick days scale the cost factor relative to this reference situation.
WORKDAYS_PER_YEAR = 261
PUBLIC_HOLIDAYS = 8
REFERENCE_VACATION_DAYS = 25
REFERENCE_SICK_DAYS = 8
