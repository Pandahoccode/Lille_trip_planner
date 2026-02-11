"""
Fetch daily weather forecast for Lille via Open-Meteo.

Uses the openmeteo-requests SDK with caching and retry.
Exports daily_weather_data.csv to data/.
"""

import os

import argparse
import sys
import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

# Add src to path for verification import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


# ---- WMO weather-code mapping ----
WEATHER_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Heavy rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherClient:
    """
    Open-Meteo daily-forecast client (free, no API key).

    Fetches weather_code, temperatures, sunrise/sunset, daylight
    duration for a given location and exports a CSV.
    """

    API_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, lat=50.62, lon=3.06, timezone="Europe/Paris",
                 past_days=21, cache_dir=".cache"):
        self.lat = lat
        self.lon = lon
        self.timezone = timezone
        self.past_days = past_days

        # Cached + retry session
        cache_session = requests_cache.CachedSession(
            os.path.join(cache_dir, "weather_cache"),
            expire_after=3600,
        )
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        self.client = openmeteo_requests.Client(session=retry_session)

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    def fetch_daily(self):
        """Return a pandas DataFrame of daily weather data."""

        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "sunrise",
                "sunset",
                "daylight_duration",
            ],
            "models": "meteofrance_seamless",
            "timezone": self.timezone,
            "past_days": self.past_days,
        }

        responses = self.client.weather_api(self.API_URL, params=params)
        response = responses[0]

        print(f"Coordinates: {response.Latitude()}°N {response.Longitude()}°E")
        print(f"Elevation: {response.Elevation()} m asl")
        print(f"Timezone: {response.Timezone()}{response.TimezoneAbbreviation()}")

        daily = response.Daily()

        daily_weather_code = daily.Variables(0).ValuesAsNumpy()
        daily_temp_max = daily.Variables(1).ValuesAsNumpy()
        daily_temp_min = daily.Variables(2).ValuesAsNumpy()
        daily_sunrise = daily.Variables(3).ValuesInt64AsNumpy()
        daily_sunset = daily.Variables(4).ValuesInt64AsNumpy()
        daily_daylight = daily.Variables(5).ValuesAsNumpy()

        dates = pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left",
        )

        df = pd.DataFrame({
            "date": dates,
            "weather_code": daily_weather_code.astype(int),
            "temperature_max": daily_temp_max,
            "temperature_min": daily_temp_min,
            "sunrise": pd.to_datetime(daily_sunrise, unit="s", utc=True)
                          .tz_convert(self.timezone),
            "sunset": pd.to_datetime(daily_sunset, unit="s", utc=True)
                        .tz_convert(self.timezone),
            "daylight_duration_s": daily_daylight,
            "daylight_duration_h": daily_daylight / 3600.0,
        })

        # Add human-readable weather description
        df.insert(
            df.columns.get_loc("weather_code") + 1,
            "weather_description",
            df["weather_code"].map(WEATHER_MAP),
        )

        return df

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    @staticmethod
    def export_csv(df, filename):
        df.to_csv(filename, index=False)
        print(f"Saved: {filename}")

    # ------------------------------------------------------------------
    # High-level
    # ------------------------------------------------------------------
    def execute(self):
        df = self.fetch_daily()
        print("\nDaily data with descriptions\n", df)

        out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "daily_weather_data.csv")

        self.export_csv(df, out_path)


def verify_service():
    """Run verification logic (formerly repro_weather.py)"""
    from src.services import WeatherService

    print("Running WeatherService verification...")
    try:
        ws = WeatherService()
        print("Weather data loaded.")
        if ws.weather_df is not None:
            print(ws.weather_df.head())
            print(ws.weather_df.tail())

        # Use a future date relative to now, or the specific date that was failing
        start_date = "2026-02-14"
        forecast = ws.get_forecast(start_date)
        print(f"\nForecast for {start_date}")
        print(forecast)

        # Simulate app usage
        for _, row in forecast.iterrows():
            tmax = f"{float(row.get('temperature_max', 0)):.0f}"
            print(f"Date: {row.get('date')}, Max: {tmax}")

    except Exception as e:
        print("\nCAUGHT EXCEPTION:")
        print(e)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch weather data or verify service.")
    parser.add_argument("--verify", action="store_true", help="Run verification logic")
    args = parser.parse_args()

    if args.verify:
        verify_service()
    else:
        client = WeatherClient()
        client.execute()
