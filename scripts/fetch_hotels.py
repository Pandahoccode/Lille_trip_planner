"""Fetch hotel/accommodation data for a city from OpenDataSoft."""

from scripts.utils import extract_lat_lon, export_csv, fetch_all_paginated, get_first_non_empty

DATASET_URL = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/osm-france-tourism-accommodation/records"


def fetch_hotels(city, timeout=15):
    """Fetch and clean all hotel records for a city."""
    raw = fetch_all_paginated(
        DATASET_URL,
        base_params={"refine": f"meta_name_com:{city}"},
        timeout=timeout,
    )
    return [_clean_record(r, city) for r in raw]


def _clean_record(r, city):
    lat, lon = extract_lat_lon(r)
    return {
        "name": get_first_non_empty(r, ["name", "nom", "osm_name"]),
        "type": get_first_non_empty(r, ["tourism", "accommodation", "type"]),
        "description": None,
        "stars": get_first_non_empty(r, ["stars", "classification"]),
        "website": get_first_non_empty(r, ["website"]),
        "phone": get_first_non_empty(r, ["phone"]),
        "city": r.get("meta_name_com", city),
        "department": r.get("meta_name_dep"),
        "region": r.get("meta_name_reg"),
        "latitude": lat,
        "longitude": lon,
    }


if __name__ == "__main__":
    rows = fetch_hotels("Lille")
    print(f"Hotels fetched: {len(rows)}")
    coords = sum(1 for x in rows if x["latitude"] is not None)
    print(f"With coordinates: {coords}")
    export_csv(f"hotels_lille.csv", rows)
    print("CSV generated: hotels_lille.csv")
