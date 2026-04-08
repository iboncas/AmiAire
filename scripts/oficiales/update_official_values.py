#!/usr/bin/env python3
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def load_environment() -> None:
    root_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(root_env)


def to_float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def fetch_batch(stations: List[Dict[str, Any]], timeout_seconds: int) -> List[Dict[str, Any]]:
    latitudes = ",".join(str(s["lat"]) for s in stations)
    longitudes = ",".join(str(s["long"]) for s in stations)
    query = urlencode(
        {
            "latitude": latitudes,
            "longitude": longitudes,
            "current": "pm2_5,pm10",
        }
    )
    url = f"{OPEN_METEO_URL}?{query}"
    req = Request(url, headers={"User-Agent": "amiaire-official-updater/1.0"})

    with urlopen(req, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))

    entries = payload if isinstance(payload, list) else [payload]
    now_iso = datetime.now(timezone.utc).isoformat()

    out: List[Dict[str, Any]] = []
    for idx, _station in enumerate(stations):
        current = entries[idx].get("current", {}) if idx < len(entries) else {}
        out.append(
            {
                "pm25": to_float_or_none(current.get("pm2_5")),
                "pm10": to_float_or_none(current.get("pm10")),
                "fetched_at": current.get("time") or now_iso,
            }
        )
    return out


def run(
    mongo_uri: str,
    db_name: str,
    collection_name: str,
    batch_size: int,
    timeout_seconds: int,
    sleep_seconds: float,
    max_station_requests_per_minute: int,
) -> Dict[str, Any]:
    client = MongoClient(mongo_uri)
    try:
        collection = client[db_name][collection_name]
        stations = list(collection.find({}, {"_id": 0, "id": 1, "lat": 1, "long": 1}))
        valid_stations = [
            s
            for s in stations
            if s.get("id")
            and isinstance(s.get("lat"), (int, float))
            and isinstance(s.get("long"), (int, float))
            and math.isfinite(float(s["lat"]))
            and math.isfinite(float(s["long"]))
        ]

        total = len(valid_stations)
        if total == 0:
            return {
                "success": True,
                "message": "No valid stations to update",
                "collection": f"{db_name}.{collection_name}",
                "total_stations": 0,
                "updated": 0,
                "failed_batches": 0,
            }

        updated = 0
        failed_batches = 0
        total_batches = math.ceil(total / batch_size)

        # Quota is enforced per station request (not per batch request).
        # If quota=600 station-requests/min and we have 776 stations, total runtime
        # will be at least 776/600*60 = 77.6 seconds (> 1 minute).
        started_at = time.monotonic()
        sent_station_requests = 0

        for start in range(0, total, batch_size):
            batch = valid_stations[start : start + batch_size]
            try:
                if max_station_requests_per_minute > 0 and sent_station_requests > 0:
                    required_elapsed = (
                        sent_station_requests / max_station_requests_per_minute
                    ) * 60.0
                    elapsed = time.monotonic() - started_at
                    wait_seconds = required_elapsed - elapsed
                    if wait_seconds > 0:
                        time.sleep(wait_seconds)

                values = fetch_batch(batch, timeout_seconds=timeout_seconds)
                sent_station_requests += len(batch)
                ops = []
                for station, value in zip(batch, values):
                    ops.append(
                        UpdateOne(
                            {"id": station["id"]},
                            {
                                "$set": {
                                    "pm25": value["pm25"],
                                    "pm10": value["pm10"],
                                    "fetched_at": value["fetched_at"],
                                }
                            },
                        )
                    )
                if ops:
                    result = collection.bulk_write(ops, ordered=False)
                    updated += result.modified_count
            except Exception as exc:
                failed_batches += 1
                print(
                    f"[WARN] Batch {start // batch_size + 1}/{total_batches} failed: {exc}",
                    flush=True,
                )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        return {
            "success": True,
            "collection": f"{db_name}.{collection_name}",
            "total_stations": total,
            "updated": updated,
            "failed_batches": failed_batches,
            "batch_size": batch_size,
            "max_station_requests_per_minute": max_station_requests_per_minute,
        }
    finally:
        client.close()


def main() -> None:
    load_environment()

    parser = argparse.ArgumentParser(
        description="Update tfg.official station pm values from Open-Meteo."
    )
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI") or os.getenv("MONGODB_URI"))
    parser.add_argument("--db", default=os.getenv("MONGODB_DATABASE", "tfg"))
    parser.add_argument("--collection", default=os.getenv("OFFICIAL_COLLECTION", "official"))
    parser.add_argument(
        "--batch-size", type=int, default=int(os.getenv("OFFICIAL_UPDATE_BATCH_SIZE", "80"))
    )
    parser.add_argument(
        "--timeout", type=int, default=int(os.getenv("OFFICIAL_UPDATE_TIMEOUT_SECONDS", "20"))
    )
    parser.add_argument(
        "--sleep", type=float, default=float(os.getenv("OFFICIAL_UPDATE_SLEEP_SECONDS", "0.2"))
    )
    parser.add_argument(
        "--max-rpm",
        type=int,
        default=int(os.getenv("OFFICIAL_UPDATE_MAX_RPM", "600")),
        help="Max station-requests/minute (quota enforced as if each station is one request).",
    )
    args = parser.parse_args()

    if not args.mongo_uri:
        raise SystemExit("Missing Mongo URI. Set MONGO_URI or pass --mongo-uri.")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if args.max_rpm <= 0:
        raise SystemExit("--max-rpm must be > 0")

    summary = run(
        mongo_uri=args.mongo_uri,
        db_name=args.db,
        collection_name=args.collection,
        batch_size=args.batch_size,
        timeout_seconds=args.timeout,
        sleep_seconds=args.sleep,
        max_station_requests_per_minute=args.max_rpm,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
