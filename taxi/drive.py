import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def base_minutes(t: dict, a: str, b: str) -> int:
    return t["same_area_min"] if a == b else t["minutes"][(a, b)]


def drive_minutes(t: dict, a: str, b: str, depart_minute: int) -> int:
    if a == b:
        return t["same_area_min"]
    m = base_minutes(t, a, b)
    peak_start, peak_end, peak_factor = t["peak"]
    late_start, late_factor = t["late"]
    if peak_start <= depart_minute < peak_end:
        m *= peak_factor
    if depart_minute >= late_start:
        m *= late_factor
    return round(m)


# shortcut: straight-line nearest area, upgrade to suburb polygons if far suburbs get mis-mapped
def nearest_area(t: dict, lat: float, lon: float, max_km: float) -> str | None:
    name, km = min(((n, haversine_km(lat, lon, *ll)) for n, ll in t["areas"].items()), key=lambda x: x[1])
    return name if km <= max_km else None
