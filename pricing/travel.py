"""Travel distance and cost estimation for Hackathon."""

import urllib.parse
import urllib.request
import json
from decimal import Decimal, ROUND_HALF_UP

# Belastingdienst constants (Updated for 2026)
TAX_FREE_RATE_PER_KM = Decimal("0.25")
WORKABLE_DAYS_PER_YEAR_FULL_TIME = Decimal("214")
FULL_TIME_DAYS_PER_WEEK = Decimal("5")
MONTHS_IN_YEAR = Decimal("12")


def geocode(location: str) -> tuple[float, float] | None:
    """Free text-to-coordinates using OpenStreetMap (Restored name to fix API imports)."""
    if not location:
        return None
        
    query = urllib.parse.urlencode({"q": location, "format": "json", "limit": 1, "countrycodes": "nl"})
    url = f"https://nominatim.openstreetmap.org/search?{query}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "HackathonHRApp/1.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception as e:
        print(f"Geocoding failed for {location}: {e}")
        
    return None


def route_distance_km(origin: str, destination: str) -> dict | None:
    """Free routing distance using OSRM."""
    coords_a = geocode(origin)
    coords_b = geocode(destination)
    
    if not coords_a or not coords_b:
        return None
        
    route_str = f"{coords_a[1]},{coords_a[0]};{coords_b[1]},{coords_b[0]}"
    url = f"https://router.project-osrm.org/route/v1/driving/{route_str}?overview=false"
    
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            km = Decimal(data["routes"][0]["distance"]) / 1000
            return {"km": km.quantize(Decimal("0.1")), "source": "route"}
    except Exception as e:
        print(f"Routing failed: {e}")
        
    return None


def estimate_monthly_travel_cost(
    one_way_distance_km: float | Decimal,
    days_worked_per_week: float | Decimal,
    transport_method: str = "car",
    ov_subscription_cost: float | Decimal = 0.0
) -> Decimal:
    """
    Calculates the estimated monthly travel cost based on Belastingdienst formulas.
    """
    transport_method = transport_method.strip().lower()
    distance = Decimal(str(one_way_distance_km))

    if transport_method == "ov":
        if ov_subscription_cost and Decimal(str(ov_subscription_cost)) > 0:
            return Decimal(str(ov_subscription_cost)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Hackathon Heuristic: ~€8.50 per km, maxing out at €353 (NS Altijd Vrij price)
        mock_ov_cost = distance * Decimal("8.50")
        final_ov_cost = min(Decimal("353.00"), mock_ov_cost)
        return final_ov_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if transport_method in ("car", "bicycle"):
        days = Decimal(str(days_worked_per_week))
        workable_days = WORKABLE_DAYS_PER_YEAR_FULL_TIME * (days / FULL_TIME_DAYS_PER_WEEK)
        yearly_cost = (distance * 2) * workable_days * TAX_FREE_RATE_PER_KM
        monthly_cost = yearly_cost / MONTHS_IN_YEAR
        return monthly_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    raise ValueError(f"Unknown transport method: {transport_method}")