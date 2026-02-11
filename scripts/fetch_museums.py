"""Fetch historical sites / museums for a city from OpenDataSoft."""

from scripts.utils import extract_lat_lon, export_csv, fetch_all_paginated, get_first_non_empty

DATASET_URL = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/osm-france-historic/records"


def fetch_historical_sites(city, timeout=20):
    """Fetch and clean all historical site records for a city."""
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
        "description": get_first_non_empty(r, ["description"]),
        "build_date": get_first_non_empty(r, ["build_date"]),
        "heritage": get_first_non_empty(r, ["heritage"]),
        "wikipedia": get_first_non_empty(r, ["wikipedia"]),
        "religion": get_first_non_empty(r, ["religion"]),
        "denomination": get_first_non_empty(r, ["religion_denomination"]),
        "ref_mhs": get_first_non_empty(r, ["ref_mhs"]),
        "city": r.get("meta_name_com", city),
        "department": r.get("meta_name_dep"),
        "region": r.get("meta_name_reg"),
        "latitude": lat,
        "longitude": lon,
    }


if __name__ == "__main__":
    rows = fetch_historical_sites("Lille")
    print(f"Historical sites fetched: {len(rows)}")
    coords = sum(1 for x in rows if x["latitude"] is not None)
    print(f"With coordinates: {coords}")
    export_csv(f"historical_sites_lille.csv", rows)
    print("CSV generated: historical_sites_lille.csv")
