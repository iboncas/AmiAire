#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchNearby"
DEFAULT_INPUT_CSV = "iteration2/output/dataset/images_metadata.csv"
DEFAULT_CACHE_JSON = "iteration2/output/dataset/places_cache.json"
DEFAULT_OUTPUT_CSV = "iteration2/output/dataset/places_features.csv"
DEFAULT_RADIUS_METERS = 500.0
DEFAULT_MAX_RESULT_COUNT = 20
DEFAULT_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.types",
        "places.primaryType",
        "places.displayName",
        "places.location",
    ]
)

TRANSIT_TYPES = {
    "transit_station",
    "bus_station",
    "train_station",
    "subway_station",
    "light_rail_station",
}
PARK_TYPES = {"park"}
GAS_STATION_TYPES = {"gas_station"}
PARKING_TYPES = {"parking"}
INDUSTRIAL_KEYWORDS = ("industrial", "warehouse", "storage", "logistics")
MAJOR_ROAD_KEYWORDS = ("route", "intersection", "highway")


def load_environment() -> None:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / "backend" / ".env", override=False)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def csv_ready_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], preferred_columns: list[str] | None = None) -> list[str]:
    preferred_columns = preferred_columns or []
    preferred_unique: list[str] = []
    seen = set()
    for column in preferred_columns:
        if column not in seen:
            preferred_unique.append(column)
            seen.add(column)

    discovered: list[str] = []
    discovered_seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen and key not in discovered_seen:
                discovered.append(key)
                discovered_seen.add(key)

    fieldnames = [column for column in preferred_unique if any(column in row for row in rows)] + discovered
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_ready_value(row.get(field)) for field in fieldnames})
    return fieldnames


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"locations": {}}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return {"locations": {}}
    if "locations" not in payload or not isinstance(payload["locations"], dict):
        payload["locations"] = {}
    return payload


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def location_key(latitude: float, longitude: float, precision: int = 6) -> str:
    return f"{latitude:.{precision}f},{longitude:.{precision}f}"


def load_unique_locations(input_csv: Path) -> list[dict[str, Any]]:
    rows = load_csv_rows(input_csv)
    grouped: dict[str, dict[str, Any]] = {}
    sensor_ids_by_location: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        latitude = parse_float(row.get("latitude"))
        longitude = parse_float(row.get("longitude"))
        sensor_id = (row.get("sensor_id") or row.get("image_id") or "").strip()
        if latitude is None or longitude is None or not sensor_id:
            continue
        key = location_key(latitude, longitude)
        sensor_ids_by_location[key].add(sensor_id)
        grouped[key] = {
            "location_key": key,
            "latitude": latitude,
            "longitude": longitude,
        }

    locations = []
    for key in sorted(grouped):
        record = dict(grouped[key])
        record["sensor_ids"] = sorted(sensor_ids_by_location[key])
        record["sensor_count"] = len(record["sensor_ids"])
        locations.append(record)
    return locations


def request_nearby_places(
    api_key: str,
    latitude: float,
    longitude: float,
    radius_meters: float,
    max_result_count: int,
    field_mask: str,
) -> tuple[int, dict[str, Any]]:
    body = {
        "maxResultCount": max_result_count,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        },
    }
    encoded_body = json.dumps(body).encode("utf-8")
    request = Request(
        PLACES_ENDPOINT,
        data=encoded_body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return response.status, payload
    except HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": {"message": raw[:500]}}
        return error.code, payload
    except URLError as error:
        return 0, {"error": {"message": str(error)}}


def normalize_types(place: dict[str, Any]) -> set[str]:
    types = place.get("types") or []
    if not isinstance(types, list):
        return set()
    return {str(item).strip() for item in types if isinstance(item, str) and item.strip()}


def place_matches_keywords(types: set[str], keywords: tuple[str, ...]) -> bool:
    for place_type in types:
        lowered = place_type.lower()
        if any(keyword in lowered for keyword in keywords):
            return True
    return False


def categorize_place(place: dict[str, Any]) -> set[str]:
    types = normalize_types(place)
    categories: set[str] = set()

    if types & TRANSIT_TYPES:
        categories.add("transit")
    if types & PARK_TYPES:
        categories.add("park")
    if types & GAS_STATION_TYPES:
        categories.add("gas_station")
    if types & PARKING_TYPES:
        categories.add("parking")
    if place_matches_keywords(types, INDUSTRIAL_KEYWORDS):
        categories.add("industrial")
    if place_matches_keywords(types, MAJOR_ROAD_KEYWORDS):
        categories.add("major_road_proxy")

    return categories


def shannon_entropy(counts: list[int]) -> float | None:
    positive = [count for count in counts if count > 0]
    total = sum(positive)
    if total <= 0:
        return None
    entropy = 0.0
    for count in positive:
        probability = count / total
        entropy -= probability * math.log2(probability)
    return float(entropy)


def build_feature_row(location: dict[str, Any], cache_entry: dict[str, Any]) -> list[dict[str, Any]]:
    places = cache_entry.get("response", {}).get("places") or []
    if not isinstance(places, list):
        places = []

    category_counts = Counter()
    relevant_places_count = 0
    for place in places:
        if not isinstance(place, dict):
            continue
        categories = categorize_place(place)
        if categories:
            relevant_places_count += 1
        for category in categories:
            category_counts[category] += 1

    traffic_proxy = (
        category_counts["transit"]
        + category_counts["gas_station"]
        + category_counts["parking"]
        + category_counts["major_road_proxy"]
    )
    green_vs_traffic_ratio = (
        category_counts["park"] / traffic_proxy if traffic_proxy > 0 else None
    )

    query_status = cache_entry.get("query_status") or "missing"
    no_results = 1.0 if query_status == "ok" and not places else 0.0
    places_missing_flag = 0.0 if query_status == "ok" else 1.0

    base_row = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "total": relevant_places_count,
        "transit": category_counts["transit"],
        "park": category_counts["park"],
        "gas_station": category_counts["gas_station"],
        "parking": category_counts["parking"],
        "industrial": category_counts["industrial"],
        "major_road_proxy": category_counts["major_road_proxy"],
        "dominant_place_category": category_counts.most_common(1)[0][0] if category_counts else "",
        "place_diversity_entropy": shannon_entropy(list(category_counts.values())),
        "green_vs_traffic_ratio_500m": green_vs_traffic_ratio,
    }

    rows = []
    for sensor_id in location["sensor_ids"]:
        row = dict(base_row)
        row["sensor_id"] = sensor_id
        rows.append(row)
    return rows


def main() -> None:
    load_environment()

    parser = argparse.ArgumentParser(
        description="Query Google Places Nearby Search (New) for unique sensor locations and export cached air-quality proxy features."
    )
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV, help="CSV containing sensor_id, latitude, and longitude")
    parser.add_argument("--cache-json", default=DEFAULT_CACHE_JSON, help="Path to the raw Places cache JSON")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV, help="Path to the derived Places features CSV")
    parser.add_argument("--radius-meters", type=float, default=DEFAULT_RADIUS_METERS, help="Nearby search radius in meters")
    parser.add_argument("--max-result-count", type=int, default=DEFAULT_MAX_RESULT_COUNT, help="Maximum results requested per location")
    parser.add_argument("--sleep-seconds", type=float, default=0.2, help="Delay between uncached API calls")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on uncached locations to query in this run")
    parser.add_argument("--force-refresh", action="store_true", help="Re-query locations even if they already exist in the cache")
    parser.add_argument("--features-only", action="store_true", help="Do not call the API; only rebuild the derived CSV from the cache")
    parser.add_argument("--api-key-env", default="GOOGLE_MAPS_API_KEY", help="Environment variable name containing the API key")
    args = parser.parse_args()

    input_csv = Path(args.input_csv).resolve()
    cache_json = Path(args.cache_json).resolve()
    output_csv = Path(args.output_csv).resolve()
    ensure_directory(cache_json.parent)
    ensure_directory(output_csv.parent)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    api_key = os.getenv(args.api_key_env, "").strip()
    if not args.features_only and not api_key:
        raise RuntimeError(
            f"Missing Google Places API key. Set {args.api_key_env} in the environment before running this script."
        )

    locations = load_unique_locations(input_csv)
    cache = load_cache(cache_json)
    cache_locations: dict[str, Any] = cache.setdefault("locations", {})

    queried = 0
    skipped = 0
    failed = 0

    if not args.features_only:
        for location in locations:
            key = location["location_key"]
            existing = cache_locations.get(key)
            if existing and not args.force_refresh:
                skipped += 1
                continue
            if args.limit > 0 and queried >= args.limit:
                break

            status_code, payload = request_nearby_places(
                api_key=api_key,
                latitude=location["latitude"],
                longitude=location["longitude"],
                radius_meters=args.radius_meters,
                max_result_count=args.max_result_count,
                field_mask=DEFAULT_FIELD_MASK,
            )
            query_status = "ok" if status_code == 200 else "failed"
            if query_status == "failed":
                failed += 1
            cache_locations[key] = {
                "sensor_ids": location["sensor_ids"],
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "radius_m": args.radius_meters,
                "max_result_count": args.max_result_count,
                "field_mask": DEFAULT_FIELD_MASK,
                "queried_at": datetime.now(timezone.utc).isoformat(),
                "query_status": query_status,
                "status_code": status_code,
                "response": payload if isinstance(payload, dict) else {},
            }
            save_cache(cache_json, cache)
            queried += 1
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    feature_rows: list[dict[str, Any]] = []
    for location in locations:
        key = location["location_key"]
        cache_entry = cache_locations.get(key, {"query_status": "missing", "response": {}})
        feature_rows.extend(build_feature_row(location, cache_entry))

    written_columns = write_csv(
        output_csv,
        feature_rows,
        preferred_columns=[
            "sensor_id",
            "latitude",
            "longitude",
            "total",
            "transit",
            "park",
            "gas_station",
            "parking",
            "industrial",
            "major_road_proxy",
            "dominant_place_category",
            "place_diversity_entropy",
            "green_vs_traffic_ratio_500m",
        ],
    )

    summary = {
        "input_csv": str(input_csv),
        "cache_json": str(cache_json),
        "output_csv": str(output_csv),
        "unique_locations": len(locations),
        "feature_rows_written": len(feature_rows),
        "queried_locations_this_run": queried,
        "skipped_cached_locations": skipped,
        "failed_queries_this_run": failed,
        "features_only": bool(args.features_only),
        "force_refresh": bool(args.force_refresh),
        "written_columns": written_columns,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
