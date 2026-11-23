import json

WEATHER_URL = ("https://api.open-meteo.com/v1/forecast?latitude=-33.87&longitude=151.21"
               "&hourly=precipitation_probability,precipitation&timezone=Australia%2FSydney&forecast_days=7")


def rain_hours(data: dict, w: dict) -> set[str]:
    cfg, h = w["rain"], data["hourly"]
    # shortcut: one CBD forecast point; upgrade to one point per area if suburbs disagree
    return {t[:13] for t, p, mm in zip(h["time"], h["precipitation_probability"], h["precipitation"])
            if (mm or 0) >= cfg["min_mm"] or (p or 0) >= cfg["min_prob"]}


def fetch_rain(get_text, w: dict) -> set[str]:
    return rain_hours(json.loads(get_text(WEATHER_URL)), w)
