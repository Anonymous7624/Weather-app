"""
SQLite database for Past 7 Days historical weather.
Stores locations (seeded + user-added) and rolling 7-day hourly history.
Raspberry Pi friendly: minimal storage, no images, efficient indexing.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

# Default DB path: instance folder (Flask convention) or current dir
DB_PATH = os.environ.get(
    "WEATHER_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance", "weather.db"),
)

# Retention: keep only last 7 days
RETENTION_DAYS = 7


def _ensure_instance_dir():
    """Create instance directory if it doesn't exist."""
    d = os.path.dirname(DB_PATH)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


@contextmanager
def get_connection():
    """Context manager for database connections."""
    _ensure_instance_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create schema if it doesn't exist. Idempotent."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA)


def _coord_key(lat, lon):
    """Create a stable coord-based key for deduplication. One location per coordinate pair."""
    try:
        return f"{round(float(lat), 4):.4f}_{round(float(lon), 4):.4f}"
    except (TypeError, ValueError):
        return None


_SCHEMA = """
-- Locations: seeded (~1000) + user-added
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    state_region TEXT DEFAULT '',
    country TEXT NOT NULL DEFAULT 'US',
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    normalized_key TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL DEFAULT 'seeded' CHECK (source_type IN ('seeded', 'user_added')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_requested_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_locations_normalized_key ON locations(normalized_key);
CREATE INDEX IF NOT EXISTS idx_locations_source_active ON locations(source_type, is_active);
CREATE INDEX IF NOT EXISTS idx_locations_last_requested ON locations(last_requested_at);

-- Hourly history: rolling 7 days per location
CREATE TABLE IF NOT EXISTS hourly_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    temperature REAL,
    apparent_temperature REAL,
    humidity INTEGER,
    dew_point REAL,
    visibility_mi REAL,
    wind_speed_mph REAL,
    wind_direction INTEGER,
    wind_gust_mph REAL,
    pressure_inhg REAL,
    precip_probability INTEGER,
    precip_amount_in REAL,
    cloud_cover INTEGER,
    condition_code INTEGER,
    condition_text TEXT,
    UNIQUE(location_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_hourly_location_ts ON hourly_history(location_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_hourly_timestamp ON hourly_history(timestamp);
"""


def upsert_location(name, state_region, country, lat, lon, source_type="user_added"):
    """
    Insert or update a location. Returns (location_id, created).
    Deduplicates by coordinate pair (normalized_key = lat_lon).
    """
    nkey = _coord_key(lat, lon)
    if not nkey:
        return None, False

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT id, source_type FROM locations WHERE normalized_key = ?
            """,
            (nkey,),
        )
        row = cur.fetchone()
        if row:
            loc_id = row["id"]
            # Update last_requested_at; for user_added, also refresh name if we have better display info
            conn.execute(
                """
                UPDATE locations
                SET last_requested_at = ?, name = ?, state_region = ?, country = ?
                WHERE id = ?
                """,
                (now, name.strip(), (state_region or "").strip(), (country or "US").strip(), loc_id),
            )
            return loc_id, False

        conn.execute(
            """
            INSERT INTO locations (name, state_region, country, latitude, longitude, normalized_key, source_type, created_at, last_requested_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                name.strip(),
                (state_region or "").strip(),
                (country or "US").strip(),
                round(float(lat), 4),
                round(float(lon), 4),
                nkey,
                source_type,
                now,
                now,
            ),
        )
        loc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return loc_id, True


def ensure_location_tracked(display_name, lat, lon, source_type="user_added"):
    """
    Ensure a location is in the DB and return its id. Updates last_requested_at.
    Parses display_name (e.g. 'Boston, MA' or 'Near Boston, MA') for name/state.
    """
    lat_r = round(float(lat), 4)
    lon_r = round(float(lon), 4)
    existing = get_location_by_coords(lat_r, lon_r)
    if existing:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                "UPDATE locations SET last_requested_at = ? WHERE id = ?",
                (now, existing["id"]),
            )
        return existing["id"]

    # Parse display_name: "City, ST" or "Near City, ST" or "Address, City, ST"
    name = (display_name or "").strip()
    state = ""
    country = "US"
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        if len(parts) >= 2:
            # Last part might be "ST" or "ST 12345"
            last = parts[-1]
            if len(last) <= 3 and last.isalpha():
                state = last
                name = ",".join(parts[:-1]).strip()
            elif len(parts) >= 3:
                state = parts[-2] if len(parts[-2]) <= 3 else ""
                name = parts[0]
    # Remove "Near " prefix
    if name.lower().startswith("near "):
        name = name[5:].strip()
    if not name:
        name = f"{lat_r}, {lon_r}"

    loc_id, _ = upsert_location(name, state, country, lat_r, lon_r, source_type)
    return loc_id


def get_location_by_coords(lat, lon):
    """Get location by coordinates (within rounding). Returns dict or None."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT id, name, state_region, country, latitude, longitude, normalized_key, source_type, created_at, last_requested_at, is_active
            FROM locations
            WHERE abs(latitude - ?) < 0.0001 AND abs(longitude - ?) < 0.0001
            LIMIT 1
            """,
            (round(float(lat), 4), round(float(lon), 4)),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_location_by_id(loc_id):
    """Get location by id. Returns dict or None."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM locations WHERE id = ? AND is_active = 1",
            (loc_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def insert_hourly_rows(location_id, rows):
    """
    Insert hourly history rows. Deduplicates by (location_id, timestamp).
    rows: list of dicts with keys matching schema columns.
    Returns count of actually inserted rows.
    """
    if not rows:
        return 0

    cols = [
        "location_id", "timestamp", "fetched_at", "temperature", "apparent_temperature",
        "humidity", "dew_point", "visibility_mi", "wind_speed_mph", "wind_direction",
        "wind_gust_mph", "pressure_inhg", "precip_probability", "precip_amount_in",
        "cloud_cover", "condition_code", "condition_text",
    ]
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with get_connection() as conn:
        for r in rows:
            ts = r.get("timestamp")
            if not ts or not location_id:
                continue
            try:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO hourly_history (location_id, timestamp, fetched_at, temperature, apparent_temperature, humidity, dew_point, visibility_mi, wind_speed_mph, wind_direction, wind_gust_mph, pressure_inhg, precip_probability, precip_amount_in, cloud_cover, condition_code, condition_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        location_id,
                        ts,
                        r.get("fetched_at") or now,
                        r.get("temperature"),
                        r.get("apparent_temperature"),
                        r.get("humidity"),
                        r.get("dew_point"),
                        r.get("visibility_mi"),
                        r.get("wind_speed_mph"),
                        r.get("wind_direction"),
                        r.get("wind_gust_mph"),
                        r.get("pressure_inhg"),
                        r.get("precip_probability"),
                        r.get("precip_amount_in"),
                        r.get("cloud_cover"),
                        r.get("condition_code"),
                        r.get("condition_text"),
                    ),
                )
                inserted += cur.rowcount
            except sqlite3.IntegrityError:
                pass
    return inserted


def prune_old_history():
    """Delete hourly history older than 7 days. Call periodically."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM hourly_history WHERE timestamp < ?", (cutoff,))
        return cur.rowcount


def get_hourly_history(location_id, limit=200):
    """
    Get hourly history for a location, most recent first.
    Returns list of dicts ready for charts.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT timestamp, temperature, apparent_temperature, humidity, dew_point,
                   visibility_mi, wind_speed_mph, wind_direction, wind_gust_mph,
                   pressure_inhg, precip_probability, precip_amount_in, cloud_cover,
                   condition_code, condition_text
            FROM hourly_history
            WHERE location_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (location_id, cutoff, limit),
        )
        return [dict(row) for row in cur.fetchall()]


def get_history_day_count(location_id):
    """Return how many unique days of history we have (max 7)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT COUNT(DISTINCT date(timestamp)) as days
            FROM hourly_history
            WHERE location_id = ? AND timestamp >= ?
            """,
            (location_id, cutoff),
        )
        row = cur.fetchone()
        return row["days"] if row else 0


def get_active_seeded_locations(limit=50):
    """Get seeded locations for background collection. Returns list of (id, lat, lon)."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT id, latitude, longitude FROM locations
            WHERE source_type = 'seeded' AND is_active = 1
            ORDER BY CASE WHEN last_requested_at IS NULL THEN 0 ELSE 1 END, last_requested_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [{"id": r["id"], "lat": r["latitude"], "lon": r["longitude"]} for r in cur.fetchall()]


def get_user_added_locations_for_collection(limit=20):
    """Get user-added locations that were recently requested (for background refresh)."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT id, latitude, longitude FROM locations
            WHERE source_type = 'user_added' AND is_active = 1 AND last_requested_at IS NOT NULL
            ORDER BY last_requested_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [{"id": r["id"], "lat": r["latitude"], "lon": r["longitude"]} for r in cur.fetchall()]
