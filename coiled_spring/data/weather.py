"""
weather.py — Open-Meteo Weather Shock Detection
Pulls real-time and historical weather data by location.
Detects severe weather events that could cause conversion dips.
No API key required.
"""

import requests
from datetime import datetime, timedelta

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL  = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL   = "https://archive-api.open-meteo.com/v1/archive"

# WMO weather codes considered severe
SEVERE_CODES = {
    55: ("Heavy drizzle", 0.3),
    65: ("Heavy rain", 0.5),
    75: ("Heavy snow", 0.6),
    77: ("Snow grains", 0.4),
    82: ("Violent rain showers", 0.7),
    85: ("Heavy snow showers", 0.65),
    86: ("Heavy snow showers", 0.7),
    95: ("Thunderstorm", 0.6),
    96: ("Thunderstorm with hail", 0.8),
    99: ("Thunderstorm with heavy hail", 0.95),
}


def geocode(location: str) -> tuple:
    """Convert a location string to (lat, lon)."""
    # Try full location first, then fall back to first word (city name only)
    for search_term in [location, location.split(",")[0].strip()]:
        resp = requests.get(GEOCODING_URL, params={"name": search_term, "count": 1}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            break
    if not results:
        raise ValueError(f"Could not geocode location: {location}")
    r = results[0]
    return r["latitude"], r["longitude"]


def get_current_weather(location: str) -> dict:
    """
    Get current weather conditions for a location.
    Returns weather data with severity assessment.
    """
    lat, lon = geocode(location)

    resp = requests.get(FORECAST_URL, params={
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,precipitation,weathercode,windspeed_10m",
        "daily": "precipitation_sum,weathercode",
        "forecast_days": 3,
        "timezone": "auto"
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    current = data.get("current", {})
    wmo_code = current.get("weathercode", 0)
    precipitation = current.get("precipitation", 0)
    windspeed = current.get("windspeed_10m", 0)

    severity = assess_weather_severity(wmo_code, precipitation, windspeed)

    return {
        "location": location,
        "latitude": lat,
        "longitude": lon,
        "temperature": current.get("temperature_2m"),
        "precipitation": precipitation,
        "windspeed": windspeed,
        "weathercode": wmo_code,
        "description": SEVERE_CODES.get(wmo_code, (f"Code {wmo_code}", 0))[0],
        "severity": severity,
        "is_severe": severity >= 0.4,
        "timestamp": datetime.now().isoformat()
    }


def assess_weather_severity(wmo_code: int, precipitation: float, windspeed: float) -> float:
    """
    Compute a severity score 0.0–1.0 from weather conditions.
    Combines WMO code severity with precipitation and wind intensity.
    """
    base_severity = SEVERE_CODES.get(wmo_code, (None, 0.0))[1]

    # Boost severity for heavy precipitation
    precip_boost = min(0.3, precipitation / 50.0)

    # Boost severity for high winds (>50 km/h)
    wind_boost = min(0.2, max(0, (windspeed - 50) / 100.0))

    return round(min(1.0, base_severity + precip_boost + wind_boost), 3)


def get_weather_shocks(location: str, days_back: int = 14) -> list:
    """
    Detect severe weather events in the past N days for a location.
    Returns list of shock dicts for use in detection engine.
    """
    lat, lon = geocode(location)
    end_date = (datetime.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    resp = requests.get(ARCHIVE_URL, params={
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "precipitation_sum,weathercode,windspeed_10m_max",
        "timezone": "auto"
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json().get("daily", {})

    dates     = data.get("time", [])
    precips   = data.get("precipitation_sum", [])
    codes     = data.get("weathercode", [])
    winds     = data.get("windspeed_10m_max", [])

    shocks = []
    for i, date in enumerate(dates):
        code  = codes[i] if i < len(codes) else 0
        precip = precips[i] if i < len(precips) else 0
        wind   = winds[i] if i < len(winds) else 0
        severity = assess_weather_severity(code or 0, precip or 0, wind or 0)

        if severity >= 0.4:
            label, _ = SEVERE_CODES.get(code, (f"Severe weather (code {code})", severity))
            shocks.append({
                "shock_type": "weather",
                "description": f"{label} on {date}",
                "severity": severity,
                "start_date": date,
                "location": location,
                "source": "open_meteo",
                "details": {
                    "precipitation_mm": precip,
                    "windspeed_kmh": wind,
                    "wmo_code": code
                }
            })

    return shocks


if __name__ == "__main__":
    test_location = "Houston"
    print(f"Testing weather for: {test_location}\n")

    current = get_current_weather(test_location)
    print(f"Current conditions:")
    print(f"  Description : {current['description']}")
    print(f"  Precipitation: {current['precipitation']} mm")
    print(f"  Wind speed  : {current['windspeed']} km/h")
    print(f"  Severity    : {current['severity']}")
    print(f"  Severe?     : {current['is_severe']}\n")

    shocks = get_weather_shocks(test_location, days_back=14)
    print(f"Weather shocks in last 7 days: {len(shocks)}")
    for s in shocks:
        print(f"  {s['start_date']}: {s['description']} (severity: {s['severity']})")
