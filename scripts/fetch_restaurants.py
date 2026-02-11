"""Fetch restaurant data for a city from OpenDataSoft."""

from scripts.utils import extract_lat_lon, export_csv, fetch_all_paginated, get_first_non_empty

DATASET_URL = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/osm-france-food-service/records"


def fetch_restaurants(city, timeout=20):
    """Fetch and clean all restaurant records for a city."""
    raw = fetch_all_paginated(
        DATASET_URL,
        base_params={"refine": f"meta_name_com:{city}"},
        timeout=timeout,
    )
    return [_clean_record(r, city) for r in raw]


def _clean_record(r, city):
    lat, lon = extract_lat_lon(r)
    return {
        "name": get_first_non_empty(r, ["name"]),
        "type": get_first_non_empty(r, ["type"]),
        "cuisine": get_first_non_empty(r, ["cuisine"]),
        "brand": get_first_non_empty(r, ["operator", "brand"]),
        "vegetarian": get_first_non_empty(r, ["vegetarian"]),
        "vegan": get_first_non_empty(r, ["vegan"]),
        "delivery": get_first_non_empty(r, ["delivery"]),
        "takeaway": get_first_non_empty(r, ["takeaway"]),
        "michelin_stars": get_first_non_empty(r, ["stars"]),
        "capacity": get_first_non_empty(r, ["capacity"]),
        "phone": get_first_non_empty(r, ["phone"]),
        "website": get_first_non_empty(r, ["website"]),
        "city": r.get("meta_name_com", city),
        "department": r.get("meta_name_dep"),
        "region": r.get("meta_name_reg"),
        "latitude": lat,
        "longitude": lon,
    }


if __name__ == "__main__":
    rows = fetch_restaurants("Lille")
    print(f"Restaurants fetched: {len(rows)}")
    coords = sum(1 for x in rows if x["latitude"] is not None)
    print(f"With coordinates: {coords}")
    export_csv("restaurants_lille.csv", rows)
    print("CSV generated: restaurants_lille.csv")
