#!/usr/bin/env python3
"""
Seed the weather database with ~1000 important US locations.
Run from project root: python scripts/seed_locations.py

Supports:
- JSON file: data/seed_locations.json
- Extend the JSON to add more cities (name, state, lat, lon)
- Easy to maintain: edit JSON and re-run
"""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import init_db, upsert_location


def load_seed_json(path):
    """Load locations from JSON file. Returns list of dicts."""
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    return data


def run_seed(json_path=None):
    """Seed the database with locations from JSON."""
    if json_path is None:
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "seed_locations.json"
        )
    if not os.path.isfile(json_path):
        print(f"Seed file not found: {json_path}")
        print("Create data/seed_locations.json with format:")
        print('  [{"name": "Boston", "state": "MA", "lat": 42.36, "lon": -71.06}, ...]')
        sys.exit(1)

    init_db()
    locations = load_seed_json(json_path)
    inserted = 0
    updated = 0

    for loc in locations:
        name = loc.get("name", "").strip()
        state = loc.get("state", "").strip()
        country = loc.get("country", "US").strip()
        lat = loc.get("lat")
        lon = loc.get("lon")
        if not name or lat is None or lon is None:
            continue
        loc_id, created = upsert_location(
            name=name,
            state_region=state,
            country=country,
            lat=lat,
            lon=lon,
            source_type="seeded",
        )
        if created:
            inserted += 1
        else:
            updated += 1

    print(f"Seed complete: {inserted} inserted, {updated} already existed")
    print(f"Total locations in seed file: {len(locations)}")


if __name__ == "__main__":
    run_seed()
