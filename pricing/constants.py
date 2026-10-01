"""Pricing defaults and assumptions (owner: Teun).

Values marked ASSUMPTION are our own interpretation and must be validated with the client.
"""

from decimal import Decimal

# "Kostprijsfactor": total employer cost ≈ 2× gross wage. Vacation days, sick leave and other
# secondary employment conditions are all included in this factor.
DEFAULT_COST_FACTOR = Decimal("2.0")

# Recruiter margin in € per hour on top of the all-in cost price
DEFAULT_MARGIN = Decimal("10.00")
MIN_MARGIN = Decimal("0.00")
MAX_MARGIN = Decimal("25.00")

DEFAULT_HOURS_PER_WEEK = Decimal("40")

# Monthly ↔ weekly conversion used by the client: weekly = monthly × 3 ÷ 13
MONTH_TO_WEEK = Decimal(3) / Decimal(13)

# Warning when the advised rate is more than this fraction BELOW the client's max rate
# ("candidates get rejected for being too cheap").
TOO_LOW_THRESHOLD = Decimal("0.10")

# ASSUMPTION: travel cost per km (return trip is counted), by transport type.
# Car = Dutch tax-free mileage allowance; public transport = average 2nd class fare per km.
TRAVEL_RATE_PER_KM = {
    "car": Decimal("0.23"),
    "ov": Decimal("0.20"),
}
HOURS_PER_WORKDAY = Decimal("8")
MAX_WORKDAYS_PER_WEEK = 5
