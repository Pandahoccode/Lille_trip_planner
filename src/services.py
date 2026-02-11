"""
Services for Lille Command Center.
Encapsulates external data interactions: POIs, Weather, Trains, Wikipedia.
"""

import csv
import math
import os
import json
import time
from datetime import datetime
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# Load enrivonment variables (e.g. SNCF_API_KEY)
load_dotenv()


class ServiceError(Exception):
    """Custom exception for service-related errors."""
    pass


# ── POI Service ─────────────────────────────────────────────────────────────

class POIService:
    """Handles loading of Hotels, Restaurants, and Historical Sites."""

    def __init__(self, csv_dir="data"):
        self.csv_dir = csv_dir

    def _read_csv(self, filename):
        path = os.path.join(self.csv_dir, filename)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                return list(csv.DictReader(f, delimiter=";"))
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return []

    def _clean_coords(self, items):
        """Convert latitude/longitude to float."""
        cleaned = []
        for item in items:
            try:
                if item.get("latitude") and item.get("longitude"):
                    item["latitude"] = float(item["latitude"])
                    item["longitude"] = float(item["longitude"])
                    cleaned.append(item)
            except (ValueError, TypeError):
                continue
        return cleaned

    def load_destination(self, city_name):
        """Load all POIs for a specific city."""
        city_slug = city_name.lower()
        hotels = self._read_csv(f"hotels_{city_slug}.csv")
        restaurants = self._read_csv(f"restaurants_{city_slug}.csv")
        sites = self._read_csv(f"historical_sites_{city_slug}.csv")

        return (
            self._clean_coords(hotels),
            self._clean_coords(restaurants),
            self._clean_coords(sites)
        )


# ── Weather Service ─────────────────────────────────────────────────────────

class WeatherService:
    """Handles weather data loading and forecasting."""

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.weather_df = self._load_data()

    def _load_data(self):
        # Try multiple filenames
        for name in ["daily_weather_data.csv", "weather.csv"]:
            path = os.path.join(self.data_dir, name)
            if os.path.exists(path):
                try:
                    df = pd.read_csv(path)
                    # Standardize date column
                    if "date" in df.columns:
                        df["_parsed_date"] = pd.to_datetime(
                            df["date"], errors="coerce", utc=True
                        ).dt.tz_localize(None)

                    # Filter invalid rows (missing temp or huge negative codes)
                    df = df.dropna(subset=["temperature_max", "temperature_min"])
                    if "weather_code" in df.columns:
                        df = df[df["weather_code"] > -1000] # simple check for valid codes

                    return df
                except Exception as e:
                    print(f"Error loading weather data: {e}")
        return None

    def get_forecast(self, start_date, days_past=3, days_future=2):
        """Return a DataFrame row slice for the requested period."""
        if self.weather_df is None or self.weather_df.empty:
            return pd.DataFrame()

        start_dt = pd.Timestamp(start_date)

        # Filter based on parsed dates
        past_mask = self.weather_df["_parsed_date"] < start_dt
        future_mask = self.weather_df["_parsed_date"] >= start_dt

        past_rows = self.weather_df.loc[past_mask].tail(days_past)
        future_rows = self.weather_df.loc[future_mask].head(days_future)

        return pd.concat([past_rows, future_rows])

    def get_current_weather(self):
        """Return the most recent weather data point."""
        if self.weather_df is None or self.weather_df.empty:
            return None
        return self.weather_df.iloc[-1]


# ── Train Service ───────────────────────────────────────────────────────────

class TrainService:
    """Handles SNCF API interactions and trip caching."""

    BASE_URL = "https://api.sncf.com/v1/coverage/sncf"
    CACHE_FILE = "train_trips.csv"

    def __init__(self, api_key=None, data_dir="data"):
        self.api_key = api_key or os.getenv("SNCF_API_KEY")
        self.data_dir = data_dir
        self.cache_path = os.path.join(data_dir, self.CACHE_FILE)

    def _get_station_id(self, city):
        if not self.api_key:
            raise ServiceError("SNCF_API_KEY not configured")

        url = f"{self.BASE_URL}/places"
        params = {"q": city, "type[]": "stop_area"}

        try:
            r = requests.get(url, params=params, auth=HTTPBasicAuth(self.api_key, ""))
            r.raise_for_status()
            data = r.json()
            for place in data.get("places", []):
                if place.get("embedded_type") == "stop_area":
                    return place["id"]
        except Exception as e:
            raise ServiceError(f"Station lookup failed for {city}: {e}")

        raise ServiceError(f"No station found for {city}")

    def _get_journeys(self, from_id, to_id, travel_date):
        url = f"{self.BASE_URL}/journeys"
        dt_str = travel_date.strftime("%Y%m%dT000000")
        params = {"from": from_id, "to": to_id, "datetime": dt_str, "count": 10}

        try:
            r = requests.get(url, params=params, auth=HTTPBasicAuth(self.api_key, ""))
            r.raise_for_status()
            return r.json().get("journeys", [])
        except Exception as e:
            raise ServiceError(f"Journey search failed: {e}")

    @staticmethod
    def _format_sncf_datetime(dt_str):
        try:
            dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
            return dt.strftime("%d-%m-%Y %H:%M")
        except ValueError:
            return dt_str

    @staticmethod
    def _duration_hours(seconds):
        return round(seconds / 3600, 2)

    @staticmethod
    def _extract_price(j):
        """Extract price from journey object safely."""
        try:
            if j.get("fare") and j["fare"].get("total"):
                val = j["fare"]["total"].get("value")
                # Debug print
                print(f"DEBUG PRICE: {val} (type: {type(val)})")
                # API sometimes returns "N/A" string? Handle safe cast
                if val is not None and str(val).upper() != "N/A":
                    return float(val)
        except (ValueError, TypeError) as e:
            print(f"DEBUG PRICE ERROR: {e}")
            pass
        return 0.0

    @staticmethod
    def _extract_stations(j):
        """Extract departure and arrival station names from journey sections."""
        dep = ""
        arr = ""
        try:
            sections = j.get("sections", [])
            if sections:
                # First section 'from' is departure
                dep = sections[0].get("from", {}).get("name", "")
                # Last section 'to' is arrival
                arr = sections[-1].get("to", {}).get("name", "")
        except Exception:
            pass
        return dep, arr

    def search_trips(self, cities, start_date, end_date):
        """Fetch trips from multiple cities to Lille and back."""
        results = []
        try:
            lille_id = self._get_station_id("Lille")

            for city in cities:
                city = city.strip()
                if not city: continue

                city_id = self._get_station_id(city)

                # Outbound: City -> Lille
                outbound = self._get_journeys(city_id, lille_id, start_date)
                for j in outbound:
                    results.append({
                        "from": city,
                        "to": "Lille",
                        "departure": self._format_sncf_datetime(j["departure_date_time"]),
                        "arrival": self._format_sncf_datetime(j["arrival_date_time"]),
                        "duration_hours": self._duration_hours(j["duration"]),
                        "departure_station": self._extract_stations(j)[0],
                        "arrival_station": self._extract_stations(j)[1],
                        "price": self._extract_price(j)
                    })

                # Return: Lille -> City
                inbound = self._get_journeys(lille_id, city_id, end_date)
                for j in inbound:
                    results.append({
                        "from": "Lille",
                        "to": city,
                        "departure": self._format_sncf_datetime(j["departure_date_time"]),
                        "arrival": self._format_sncf_datetime(j["arrival_date_time"]),
                        "duration_hours": self._duration_hours(j["duration"]),
                        "price": self._extract_price(j)
                    })

            # Cache results
            if results:
                self._save_cache(results)

            return results
        except ServiceError as e:
            return {"error": str(e)}

    def _save_cache(self, rows):
        os.makedirs(self.data_dir, exist_ok=True)
        keys = ["from", "to", "departure", "arrival", "duration_hours", "price", "departure_station", "arrival_station"]
        try:
            with open(self.cache_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            print(f"Failed to save cache: {e}")

    def load_cache(self):
        """Load trips from CSV cache."""
        if os.path.exists(self.cache_path):
            try:
                return pd.read_csv(self.cache_path)
            except Exception:
                pass
        return None


# ── Wikipedia Service ───────────────────────────────────────────────────────

class WikiService:
    """Handles Wikipedia summary fetching."""

    def __init__(self, lang="en"):
        self.lang = lang

    def get_summary(self, title, sentences=30):
        try:
            import wikipedia
            wikipedia.set_lang(self.lang)
            summary = wikipedia.summary(title, sentences=sentences)

            # Truncate to approx 200 words but keep sentence boundaries
            words = summary.split()
            if len(words) > 200:
                shortened = " ".join(words[:200])
                # Try to end at the last period
                last_period = shortened.rfind('.')
                if last_period != -1:
                    shortened = shortened[:last_period+1]
                return shortened

            return summary
        except Exception as e:
            print(f"Wikipedia fetch error: {e}")
            return None


# ── Route Service ───────────────────────────────────────────────────────────

class RouteService:
    """ORS client: geocoding, directions, cost estimation."""

    ORS_BASE = "https://api.openrouteservice.org"

    def __init__(self, api_key=None, cache_dir="data/.cache", timeout=20):
        self.timeout = timeout
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.api_key = api_key or os.getenv("ORS_API_KEY")

        # Constants from original script
        self.FUEL_PRICE_EUR_L = 1.75
        self.AVG_CONSUMPTION_L_100KM = 6.0
        self.TOLL_EUR_KM = 9.5 / 100.0

    def _get_headers(self):
        return {"Authorization": self.api_key}

    def _cache_path(self, prefix, key):
        safe = "".join(c for c in key.lower() if c.isalnum() or c in "_-.,[] ")
        return os.path.join(self.cache_dir, f"{prefix}_{safe}.json")

    def _cache_load(self, prefix, key, max_age=7 * 86400):
        path = self._cache_path(prefix, key)
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > max_age:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _cache_save(self, prefix, key, data):
        with open(self._cache_path(prefix, key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def geocode_city(self, city, country="FR"):
        if not self.api_key:
            return None, city

        cache_key = f"{city}_{country}"
        cached = self._cache_load("geocode", cache_key)
        if cached:
            return cached["coords"], cached.get("label", "")

        try:
            url = f"{self.ORS_BASE}/geocode/search"
            params = {"text": city, "boundary.country": country, "size": 1}
            r = requests.get(url, headers=self._get_headers(), params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()

            features = data.get("features", [])
            if not features:
                return None, city

            best = features[0]
            coords = best["geometry"]["coordinates"]
            label = best.get("properties", {}).get("label", city)
            self._cache_save("geocode", cache_key, {"coords": coords, "label": label})
            return coords, label
        except Exception as e:
            print(f"Geocode error: {e}")
            return None, city

    def calculate_route(self, coords_from, coords_to, profile="driving-car"):
        if not self.api_key or not coords_from or not coords_to:
            return {"error": "Missing API key or coordinates"}

        cache_key = f"{profile}_{coords_from}_{coords_to}"
        cached = self._cache_load("route", cache_key)
        if cached:
            return cached

        try:
            url = f"{self.ORS_BASE}/v2/directions/{profile}/geojson"
            body = {"coordinates": [coords_from, coords_to]}
            headers = self._get_headers()
            headers["Content-Type"] = "application/json"

            r = requests.post(url, headers=headers, json=body, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()

            self._cache_save("route", cache_key, data)
            return data
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def extract_metrics(route_geojson):
        features = route_geojson.get("features", [])
        if not features:
            return None, None
        summary = features[0].get("properties", {}).get("summary", {})
        return summary.get("distance"), summary.get("duration")

    def estimate_cost(self, distance_m, profile):
        if distance_m is None:
            return {}
        km = distance_m / 1000.0
        liters = (km / 100.0) * self.AVG_CONSUMPTION_L_100KM
        fuel = liters * self.FUEL_PRICE_EUR_L
        toll = km * self.TOLL_EUR_KM if profile == "driving-car" else 0.0
        return {
            "total_cost_eur": round(fuel + toll, 2),
            "fuel_cost_eur": round(fuel, 2),
            "toll_cost_eur": round(toll, 2),
            "liters_fuel": round(liters, 2),
            "distance_km": round(km, 1)
        }

    @staticmethod
    def format_duration(seconds):
        if seconds is None:
            return "N/A"
        minutes = int(round(seconds / 60))
        h, m = divmod(minutes, 60)
        return f"{h}h{m:02d}" if h > 0 else f"{m} min"

    @staticmethod
    def format_km(meters):
        if meters is None:
            return "N/A"
        return f"{meters / 1000:.1f} km"

