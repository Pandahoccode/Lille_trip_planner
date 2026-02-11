"""Shared helpers for OpenDataSoft fetch scripts."""

import csv
import requests


def get_first_non_empty(record, keys):
    """Return the first non-empty value for the given keys in a record."""
    for key in keys:
        if key in record and record[key] not in (None, "", []):
            return record[key]
    return None


def extract_lat_lon(record):
    """Extract (latitude, longitude) from a meta_geo_point field."""
    point = record.get("meta_geo_point")

    if isinstance(point, list) and len(point) == 2:
        try:
            return float(point[0]), float(point[1])
        except (TypeError, ValueError):
            return None, None

    if isinstance(point, str):
        try:
            parts = point.split(",")
            if len(parts) == 2:
                return float(parts[0].strip()), float(parts[1].strip())
        except (TypeError, ValueError):
            return None, None

    if isinstance(point, dict):
        try:
            lat = float(point["lat"]) if point.get("lat") is not None else None
            lon = float(point["lon"]) if point.get("lon") is not None else None
            return lat, lon
        except (TypeError, ValueError, KeyError):
            return None, None

    return None, None


def export_csv(filename, rows, delimiter=";"):
    """Write rows (list of dicts) to a CSV file (utf-8-sig, semicolon)."""
    if not rows:
        print("No data to export.")
        return
    with open(filename, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def fetch_all_paginated(url, base_params, timeout=20, batch_size=100):
    """Fetch all records from an OpenDataSoft endpoint with pagination."""
    if batch_size > 100:
        batch_size = 100

    all_results = []
    offset = 0

    while True:
        params = {**base_params, "limit": batch_size, "offset": offset}
        response = requests.get(url, params=params, timeout=timeout)

        if response.status_code != 200:
            print("URL:", response.url)
            print("HTTP:", response.status_code)
            print("Body:", response.text[:400])
            response.raise_for_status()

        results = response.json().get("results", [])
        if not results:
            break

        all_results.extend(results)
        offset += batch_size

    return all_results
