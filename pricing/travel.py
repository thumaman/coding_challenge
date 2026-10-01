"""Travel distance and travel costs between a candidate's home and the employer (owner: Teun).

Distance:
1. Geocode both locations (built-in table of Dutch cities first, then OpenStreetMap Nominatim).
2. Driving distance via the public OSRM routing API.
3. If routing fails: straight-line distance × ROAD_FACTOR as an estimate.
Results are cached, and every network call has a short timeout, so the UI never hangs.

Costs are calculated in engine.travel_cost_per_hour() with the €/km rates in constants.py.
A real fare API (e.g. NS for public transport) could replace those rates later.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import ssl
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

import certifi
from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)

TIMEOUT = 6  # seconds per external call
ROAD_FACTOR = 1.25  # straight line → road distance estimate

# Belastingdienst constants (Updated for 2026)
TAX_FREE_RATE_PER_KM = Decimal("0.25")
WORKABLE_DAYS_PER_YEAR_FULL_TIME = Decimal("214")
FULL_TIME_DAYS_PER_WEEK = Decimal("5")
MONTHS_IN_YEAR = Decimal("12")

# Public transport (OV): flat rate per one-way km, capped at the NS Flex Altijd Vrij subscription price
OV_RATE_PER_KM = Decimal("10.00")
NS_FLEX_ALTIJD_VRIJ_MONTH = Decimal("400.00")

# Offline coordinates for common cities: fast and demo-proof (lat, lon)
CITY_COORDS = {
    "amsterdam": (52.3702, 4.8952),
    "rotterdam": (51.9244, 4.4777),
    "den haag": (52.0705, 4.3007),
    "the hague": (52.0705, 4.3007),
    "utrecht": (52.0907, 5.1214),
    "eindhoven": (51.4416, 5.4697),
    "veldhoven": (51.4183, 5.4028),
    "amersfoort": (52.1561, 5.3878),
    "haarlem": (52.3874, 4.6462),
    "leiden": (52.1601, 4.4970),
    "groningen": (53.2194, 6.5665),
    "tilburg": (51.5555, 5.0913),
    "breda": (51.5719, 4.7683),
    "nijmegen": (51.8126, 5.8372),
    "arnhem": (51.9851, 5.8987),
    "zwolle": (52.5168, 6.0830),
    "almere": (52.3508, 5.2647),
    "delft": (52.0116, 4.3571),
    "den bosch": (51.6978, 5.3037),
    "'s-hertogenbosch": (51.6978, 5.3037),
    "maastricht": (50.8514, 5.6910),
    "enschede": (52.2215, 6.8937),
    "apeldoorn": (52.2112, 5.9699),
    "hilversum": (52.2292, 5.1669),
    "zaandam": (52.4420, 4.8292),
}


def _cache_key(*parts) -> str:
    return "travel:" + hashlib.sha1(repr(parts).encode()).hexdigest()


# certifi's CA bundle: python.org installs on macOS ship without root certificates
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _http_json(url: str):
    user_agent = getattr(settings, "TRAVEL_API_USER_AGENT", "HackathonHRApp/1.0")
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=SSL_CONTEXT) as response:
        return json.loads(response.read().decode())


def geocode(location: str) -> tuple[float, float] | None:
    """'Utrecht' / '3511 AB Utrecht' / 'Stationsplein 1, Utrecht' -> (lat, lon) or None."""
    key = (location or "").strip().lower()
    if not key:
        return None
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    cache_key = _cache_key("geo", key)
    if (hit := cache.get(cache_key)) is not None:
        return tuple(hit) if hit else None
    coords = None
    try:
        query = urllib.parse.urlencode({"q": location, "countrycodes": "nl", "format": "json", "limit": 1})
        results = _http_json(f"https://nominatim.openstreetmap.org/search?{query}")
        if results:
            coords = (float(results[0]["lat"]), float(results[0]["lon"]))
    except Exception:  # noqa: BLE001 - network problems must not break pricing
        logger.warning("Geocoding failed for %r", location, exc_info=True)
        return None
    cache.set(cache_key, coords or [], 60 * 60 * 24)
    return coords


def _haversine_km(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def route_distance_km(origin: str, destination: str) -> dict | None:
    """One-way distance between two locations.

    Returns {"km": Decimal, "source": "route" | "estimate"} or None when a location is unknown.
    """
    a, b = geocode(origin), geocode(destination)
    if not a or not b:
        return None
    cache_key = _cache_key("route", a, b)
    if (hit := cache.get(cache_key)) is not None:
        return {"km": Decimal(hit["km"]), "source": hit["source"]}
    try:
        coords = f"{a[1]},{a[0]};{b[1]},{b[0]}"
        data = _http_json(f"https://router.project-osrm.org/route/v1/driving/{coords}?overview=false")
        km = Decimal(data["routes"][0]["distance"]) / 1000
        result = {"km": km.quantize(Decimal("0.1")), "source": "route"}
    except Exception:  # noqa: BLE001
        logger.warning("Routing failed, using straight-line estimate", exc_info=True)
        km = Decimal(str(_haversine_km(a, b) * ROAD_FACTOR))
        result = {"km": km.quantize(Decimal("0.1")), "source": "estimate"}
    cache.set(cache_key, {"km": str(result["km"]), "source": result["source"]}, 60 * 60 * 24)
    return result


def offline_distance_km(origin: str, destination: str) -> Decimal | None:
    """Estimate from the built-in city table only (no network), e.g. for seeding demo data."""
    a, b = CITY_COORDS.get((origin or "").strip().lower()), CITY_COORDS.get((destination or "").strip().lower())
    if not a or not b:
        return None
    return Decimal(str(_haversine_km(a, b) * ROAD_FACTOR)).quantize(Decimal("0.1"))


def estimate_monthly_travel_cost(
    one_way_distance_km: float | Decimal,
    days_worked_per_week: float | Decimal,
    transport_method: str = "car",
    ov_subscription_cost: float | Decimal = 0.0,
) -> Decimal:
    """Calculates the estimated monthly travel cost based on Belastingdienst formulas."""
    transport_method = transport_method.strip().lower()
    distance = Decimal(str(one_way_distance_km))

    if transport_method == "ov":
        if ov_subscription_cost and Decimal(str(ov_subscription_cost)) > 0:
            return Decimal(str(ov_subscription_cost)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Hackathon heuristic: flat rate per km, capped at the NS Flex Altijd Vrij price
        final_ov_cost = min(NS_FLEX_ALTIJD_VRIJ_MONTH, distance * OV_RATE_PER_KM)
        return final_ov_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if transport_method in ("car", "bicycle"):
        days = Decimal(str(days_worked_per_week))
        workable_days = WORKABLE_DAYS_PER_YEAR_FULL_TIME * (days / FULL_TIME_DAYS_PER_WEEK)
        yearly_cost = (distance * 2) * workable_days * TAX_FREE_RATE_PER_KM
        monthly_cost = yearly_cost / MONTHS_IN_YEAR
        return monthly_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    raise ValueError(f"Unknown transport method: {transport_method}")