"""Fetch driving/cycling/walking routes via OpenRouteService (ORS)."""

import csv
import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

PROFILES = {
    "1": ("car", "driving-car"),
    "2": ("bike", "cycling-regular"),
    "3": ("walk", "foot-walking"),
}

FUEL_PRICE_EUR_L = 1.75
AVG_CONSUMPTION_L_100KM = 6.0
TOLL_EUR_KM = 9.5 / 100.0


class RouteClient:
    """ORS client: geocoding, directions, cost estimation, GeoJSON/CSV export."""

    ORS_BASE = "https://api.openrouteservice.org"

    def __init__(self, timeout=20, cache_dir=".cache"):
        self.timeout = timeout
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.api_key = os.getenv("ORS_API_KEY")
        if not self.api_key:
            raise ValueError("ORS_API_KEY not found in environment variables.")

    # HTTP helpers

    def _get(self, url, params=None):
        headers = {"Authorization": self.api_key}
        r = requests.get(url, headers=headers, params=params or {}, timeout=self.timeout)
        if r.status_code != 200:
            print("URL:", r.url, "| HTTP:", r.status_code)
            r.raise_for_status()
        return r.json()

    def _post(self, url, body=None):
        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json=body or {}, timeout=self.timeout)
        if r.status_code != 200:
            print("URL:", url, "| HTTP:", r.status_code)
            r.raise_for_status()
        return r.json()

    # Cache

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

    # Geocoding

    def geocode_city(self, city, country="FR"):
        cache_key = f"{city}_{country}"
        cached = self._cache_load("geocode", cache_key)
        if cached:
            return cached["coords"], cached.get("label", "")

        data = self._get(
            f"{self.ORS_BASE}/geocode/search",
            params={"text": city, "boundary.country": country, "size": 1},
        )
        features = data.get("features", [])
        if not features:
            raise ValueError(f"No geocoding result for: {city}")

        best = features[0]
        coords = best["geometry"]["coordinates"]
        label = best.get("properties", {}).get("label", city)
        self._cache_save("geocode", cache_key, {"coords": coords, "label": label})
        return coords, label

    # Directions

    def calculate_route(self, coords_from, coords_to, profile="driving-car"):
        cache_key = f"{profile}_{coords_from}_{coords_to}"
        cached = self._cache_load("route", cache_key)
        if cached:
            return cached

        data = self._post(
            f"{self.ORS_BASE}/v2/directions/{profile}/geojson",
            body={"coordinates": [coords_from, coords_to]},
        )
        self._cache_save("route", cache_key, data)
        return data

    # Extractions

    @staticmethod
    def extract_distance_duration(route_geojson):
        features = route_geojson.get("features", [])
        if not features:
            return None, None
        summary = features[0].get("properties", {}).get("summary", {})
        return summary.get("distance"), summary.get("duration")

    @staticmethod
    def format_km(distance_m):
        if distance_m is None:
            return "N/A"
        return f"{distance_m / 1000:.1f} km"

    @staticmethod
    def format_duration(duration_s):
        if duration_s is None:
            return "N/A"
        minutes = int(round(duration_s / 60))
        h, m = divmod(minutes, 60)
        return f"{h}h{m:02d}" if h > 0 else f"{m} min"

    # Cost estimation

    @staticmethod
    def estimate_trip_cost(distance_m, profile):
        if distance_m is None:
            return None
        km = distance_m / 1000.0
        liters = (km / 100.0) * AVG_CONSUMPTION_L_100KM
        fuel = liters * FUEL_PRICE_EUR_L
        toll = km * TOLL_EUR_KM if profile == "driving-car" else 0.0
        return {
            "distance_km": round(km, 1),
            "estimated_liters": round(liters, 2),
            "fuel_cost_eur": round(fuel, 2),
            "toll_cost_eur": round(toll, 2),
            "total_cost_eur": round(fuel + toll, 2),
        }

    # Export

    @staticmethod
    def export_geojson(filename, route_geojson):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(route_geojson, f, ensure_ascii=False, indent=2)

    @staticmethod
    def export_csv(filename, city_start, city_dest, mode, distance_km, duration, estimation):
        row = {
            "city_start": city_start,
            "city_destination": city_dest,
            "transport_mode": mode,
            "distance_km": distance_km,
            "est_duration": duration,
            "liters_fuel": (estimation or {}).get("estimated_liters"),
            "fuel_cost_eur": (estimation or {}).get("fuel_cost_eur"),
            "toll_cost_eur": (estimation or {}).get("toll_cost_eur"),
            "total_cost_eur": (estimation or {}).get("total_cost_eur"),
        }
        with open(filename, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys(), delimiter=";")
            writer.writeheader()
            writer.writerow(row)

    # Interactive CLI

    def execute(self):
        print("=== ORS TRIPS + PRICE + EXPORTS ===")
        city_start = input("Start City: ").strip()
        city_dest = input("Destination City (Enter = Lille): ").strip() or "Lille"

        print("\nTransport Mode:\n  1) Car\n  2) Bike\n  3) Walk")
        choice = input("Choice (1/2/3): ").strip() or "1"
        if choice not in PROFILES:
            choice = "1"
        mode_name, profile = PROFILES[choice]

        coords_from, label_from = self.geocode_city(city_start)
        coords_to, label_to = self.geocode_city(city_dest)
        print(f"\n  Start: {label_from} {coords_from}")
        print(f"  Dest:  {label_to} {coords_to}")
        print(f"  Mode:  {mode_name} ({profile})")

        route = self.calculate_route(coords_from, coords_to, profile)
        dist_m, dur_s = self.extract_distance_duration(route)
        print(f"\n  Distance: {self.format_km(dist_m)}")
        print(f"  Duration: {self.format_duration(dur_s)}")

        est = self.estimate_trip_cost(dist_m, profile)
        if est:
            print(f"\n  Fuel: {est['estimated_liters']} L -> {est['fuel_cost_eur']} €")
            if profile == "driving-car":
                print(f"  Toll: {est['toll_cost_eur']} €")
            print(f"  TOTAL: {est['total_cost_eur']} €")

        base = f"{city_start.lower()}_to_{city_dest.lower()}_{profile}"
        base = "".join(c for c in base if c.isalnum() or c in "_-. ")

        self.export_geojson(f"trip_{base}.geojson", route)
        self.export_csv(
            f"trip_{base}.csv", city_start, city_dest, mode_name,
            (est or {}).get("distance_km"), self.format_duration(dur_s), est,
        )
        print("Done.")


if __name__ == "__main__":
    RouteClient().execute()
