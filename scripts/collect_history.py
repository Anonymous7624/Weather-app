#!/usr/bin/env python3
"""
Background collector for Past 7 Days historical weather.
Fetches and stores hourly history for seeded and recently-viewed locations.
Run via cron (e.g. every 6 hours) for seeded locations; user-added get data on view.

Usage:
  python scripts/collect_history.py           # Collect for seeded + recent user-added
  python scripts/collect_history.py --seeded  # Seeded only
  python scripts/collect_history.py --limit 20  # Limit locations per run
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import (
    init_db,
    get_active_seeded_locations,
    get_user_added_locations_for_collection,
    insert_hourly_rows,
    prune_old_history,
)
from utils.historical import fetch_historical_hourly


def main():
    parser = argparse.ArgumentParser(description="Collect Past 7 Days weather history")
    parser.add_argument(
        "--seeded",
        action="store_true",
        help="Only collect for seeded locations",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max locations per run (default 50)",
    )
    args = parser.parse_args()

    init_db()
    prune_old_history()

    locations = []
    if args.seeded:
        locations = get_active_seeded_locations(limit=args.limit)
    else:
        seeded = get_active_seeded_locations(limit=args.limit // 2)
        user_added = get_user_added_locations_for_collection(limit=args.limit // 2)
        locations = seeded + user_added

    collected = 0
    for loc in locations:
        try:
            rows = fetch_historical_hourly(loc["lat"], loc["lon"], days=7)
            if rows:
                n = insert_hourly_rows(loc["id"], rows)
                if n > 0:
                    collected += 1
        except Exception:
            pass

    print(f"Collected history for {collected} of {len(locations)} locations")


if __name__ == "__main__":
    main()
