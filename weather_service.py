"""
ArecaMitra Backend — Weather Service
Fetches weather data from OpenWeather API and generates disease risk messages.
"""

import requests
from config import OPENWEATHER_API_KEY

FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def fetch_weather(lat: float, lon: float) -> dict:
    """
    Fetch 5-day weather forecast and extract relevant fields.

    Returns:
        dict with temperature, humidity, wind_speed, wind_direction, rainfall_total
    """
    if not OPENWEATHER_API_KEY:
        print("[Weather] WARNING: No API key set. Returning mock data.")
        return _mock_weather()

    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "lat": lat,
                "lon": lon,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        forecast_list = data.get("list", [])
        if not forecast_list:
            return _mock_weather()

        # First entry for current conditions
        first = forecast_list[0]
        main = first.get("main", {})
        wind = first.get("wind", {})

        # Sum rainfall across all forecast entries
        rainfall_total = 0.0
        for entry in forecast_list:
            rain = entry.get("rain", {})
            rainfall_total += rain.get("3h", 0.0)

        return {
            "temperature": round(main.get("temp", 0), 1),
            "humidity": main.get("humidity", 0),
            "wind_speed": round(wind.get("speed", 0), 1),
            "wind_direction": wind.get("deg", 0),
            "rainfall_total": round(rainfall_total, 1),
        }

    except requests.RequestException as e:
        print(f"[Weather] API error: {e}. Returning mock data.")
        return _mock_weather()


def _mock_weather() -> dict:
    """Fallback mock weather for when API key is unavailable."""
    return {
        "temperature": 27.0,
        "humidity": 80,
        "wind_speed": 3.0,
        "wind_direction": 200,
        "rainfall_total": 50.0,
    }


# ─── Disease Risk Thresholds ───

def generate_risk_message(disease: str, weather: dict) -> str:
    """
    Generate a contextual risk message based on disease and weather conditions.

    Risk rules:
        Koleroga HIGH: rainfall_total > 80mm AND humidity > 85%
        Koleroga MODERATE: partial match
        Yellow Leaf ELEVATED: temperature 25–32°C
        Healthy: no risk
    """
    if disease == "healthy":
        return "No disease detected. Conditions look favorable."

    rainfall = weather.get("rainfall_total", 0)
    humidity = weather.get("humidity", 0)
    temperature = weather.get("temperature", 0)

    if disease == "koleroga":
        if rainfall > 80 and humidity > 85:
            return (
                "Heavy rainfall this week significantly increases Koleroga spread risk. "
                "Immediate Bordeaux mixture spraying recommended."
            )
        elif rainfall > 50 or humidity > 75:
            return (
                "Moderate humidity and rainfall detected. "
                "Monitor for Koleroga signs and prepare preventive spraying."
            )
        else:
            return "Koleroga detected. Current weather reduces immediate spread risk, but monitor closely."

    if disease == "yellow_leaf":
        if 25 <= temperature <= 32:
            return (
                "Weather conditions favor Yellow Leaf Disease spread. "
                "Check for leafhopper activity and consider Imidacloprid application."
            )
        else:
            return "Yellow Leaf Disease detected. Current temperatures may slow spread, but continue monitoring."

    return "Disease detected. Monitor conditions and consult local agricultural officer."


def get_koleroga_zone_expansion(weather: dict) -> float:
    """
    Returns zone expansion multiplier for Koleroga based on weather.
    If rainfall > 80mm, expand warning zone by 20%.
    """
    rainfall = weather.get("rainfall_total", 0)
    if rainfall > 80:
        return 1.20  # +20% expansion
    return 1.0
