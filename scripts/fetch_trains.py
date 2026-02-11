"""
Fetch train journeys via the SNCF API.

Searches outbound & return trips between cities and Lille,
then exports results to data/train_trips.csv.
"""

import csv
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

API_KEY = os.getenv("SNCF_API_KEY")
BASE_URL = "https://api.sncf.com/v1/coverage/sncf"


# ---- Helpers ----

def format_sncf_datetime(dt_str):
    """
    Convert SNCF datetime (YYYYMMDDTHHMMSS)
    to DD/MM/YYYY HH:MM
    """
    dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
    return dt.strftime("%d-%m-%Y %H:%M")


def duration_hours(seconds):
    """
    Convert duration from seconds to hours.
    """
    return round(seconds / 3600, 2)


def extract_price(j):
    """Extract price from journey object safely."""
    try:
        if j.get("fare") and j["fare"].get("total"):
            val = j["fare"]["total"].get("value")
            # API sometimes returns "N/A" string? Handle safe cast
            if val is not None and str(val).upper() != "N/A":
                return float(val)
    except (ValueError, TypeError):
        pass
    return 0.0


# ---- Station lookup ----

def get_station_id(city):
    """
    Return the main SNCF stop_area ID for a city.
    """
    url = f"{BASE_URL}/places"
    params = {
        "q": city,
        "type[]": "stop_area"
    }

    r = requests.get(
        url,
        params=params,
        auth=HTTPBasicAuth(API_KEY, "")
    )
    r.raise_for_status()

    for place in r.json()["places"]:
        if place["embedded_type"] == "stop_area":
            return place["id"]

    raise ValueError(f"No station found for {city}")


# ---- Journeys ----

def get_journeys(from_id, to_id, travel_date):
    """
    Retrieve journeys for a full day (starting at 00:00).
    """
    url = f"{BASE_URL}/journeys"
    params = {
        "from": from_id,
        "to": to_id,
        "datetime": travel_date.strftime("%Y%m%dT000000"),
        "count": 10
    }

    r = requests.get(
        url,
        params=params,
        auth=HTTPBasicAuth(API_KEY, "")
    )
    r.raise_for_status()

    return r.json().get("journeys", [])


# ---- Multi-city search ----

def search_trips(cities, start_date, end_date):
    """
    Outbound: city -> Lille on start_date
    Return: Lille -> city on end_date
    """
    lille_id = get_station_id("Lille")
    rows = []

    for city in cities:
        try:
            city_id = get_station_id(city)

            # Outbound trips
            for j in get_journeys(city_id, lille_id, start_date):
                rows.append({
                    "from": city,
                    "to": "Lille",
                    "departure": format_sncf_datetime(j["departure_date_time"]),
                    "arrival": format_sncf_datetime(j["arrival_date_time"]),
                    "duration_hours": duration_hours(j["duration"]),
                    "price": extract_price(j)
                })

            # Return trips
            for j in get_journeys(lille_id, city_id, end_date):
                rows.append({
                    "from": "Lille",
                    "to": city,
                    "departure": format_sncf_datetime(j["departure_date_time"]),
                    "arrival": format_sncf_datetime(j["arrival_date_time"]),
                    "duration_hours": duration_hours(j["duration"]),
                    "price": extract_price(j)
                })

        except Exception as e:
            print(f"{city}: {e}")

    return rows


# ---- CSV export ----

def export_csv(filename, rows):
    """Export trip rows to a CSV file."""
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "from",
                "to",
                "departure",
                "arrival",
                "duration_hours",
                "price"
            ]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved results to {filename}")


# ---- Main ----

if __name__ == "__main__":
    cities_input = input("Enter cities (comma-separated): ")
    cities = [c.strip() for c in cities_input.split(",")]

    start_input = input("Start date & time (YYYY-MM-DD HH:MM): ")
    end_input = input("End date & time (YYYY-MM-DD HH:MM): ")

    start_dt = datetime.strptime(start_input, "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(end_input, "%Y-%m-%d %H:%M")

    results = search_trips(cities, start_dt, end_dt)

    print(f"\nFound {len(results)} trips")
    for r in results[:5]:
        print(r)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "train_trips.csv")

    export_csv(out_path, results)
