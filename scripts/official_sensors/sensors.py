#!/usr/bin/env python3
import argparse
import json
import time
from typing import Any, Dict, List, Optional

import requests

# ==============================
# CONFIG (fixed as requested)
# ==============================
API_KEY = "4af7c1aad33769b404c669a1a6ac3ecd16647109d322467e633840dd5660047c"
BASE_URL = "https://api.openaq.org/v3"
COUNTRY_ID_SPAIN = 67
PM10_ID = 1
PM25_ID = 2
FROM_DATE = "2025-01-01"

LOCATIONS_LIMIT = 1000
MEASUREMENTS_LIMIT = 1000
SLEEP_S = 0.15
MAX_RETRIES = 6
# ==============================


def request_json(
    session: requests.Session,
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    return_none_on_408: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    GET JSON with retry/backoff for 429/5xx. Optionally skip (return None) on 408 timeouts.
    """
    for attempt in range(MAX_RETRIES):
        r = session.get(url, headers=headers, params=params, timeout=timeout)

        # Success
        if 200 <= r.status_code < 300:
            return r.json()

        # OpenAQ sometimes returns 408 with a helpful message; treat it as skip when desired.
        if r.status_code == 408 and return_none_on_408:
            return None

        # Retry on transient errors
        if r.status_code in (429, 500, 502, 503, 504):
            wait = 2 ** attempt
            time.sleep(min(wait, 60))
            continue

        # Non-retriable
        raise requests.HTTPError(
            f"HTTP {r.status_code} for {r.url} -> {r.text}",
            response=r,
        )

    # Retries exhausted
    if return_none_on_408:
        return None

    raise requests.HTTPError(f"Max retries exceeded for {url}")


def fetch_locations(session: requests.Session) -> List[Dict[str, Any]]:
    """
    Fetch all locations in Spain that measure PM10 and/or PM2.5.
    """
    headers = {"X-API-Key": API_KEY}
    all_results: List[Dict[str, Any]] = []
    page = 1

    while True:
        params = {
            "countries_id": COUNTRY_ID_SPAIN,
            "parameters_id": f"{PM10_ID},{PM25_ID}",
            "limit": LOCATIONS_LIMIT,
            "page": page,
        }

        data = request_json(session, f"{BASE_URL}/locations", headers, params)
        results = (data or {}).get("results", [])
        if not results:
            break

        all_results.extend(results)

        meta = (data or {}).get("meta", {})
        total_pages = meta.get("totalPages") or meta.get("total_pages")
        if isinstance(total_pages, int) and page >= total_pages:
            break
        if len(results) < LOCATIONS_LIMIT:
            break

        page += 1
        time.sleep(SLEEP_S)

    return all_results


def pick_sensor(sensors: List[Dict[str, Any]], parameter_id: int) -> Optional[Dict[str, Any]]:
    for s in sensors or []:
        p = s.get("parameter") or {}
        if p.get("id") == parameter_id:
            return s
    return None


def collect_sensors(locations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flat list of sensors (PM10 + PM2.5) with station metadata.
    Index order is stable for slicing with --start/--end.
    """
    sensors_out: List[Dict[str, Any]] = []

    for loc in locations:
        coords = loc.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")

        sensors = loc.get("sensors") or []
        pm10 = pick_sensor(sensors, PM10_ID)
        pm25 = pick_sensor(sensors, PM25_ID)

        if pm10:
            sensors_out.append(
                {
                    "sensor_id": pm10.get("id"),
                    "parameter_name": "pm10",
                    "location_id": loc.get("id"),
                    "location_name": loc.get("name"),
                    "latitude": lat,
                    "longitude": lon,
                }
            )

        if pm25:
            sensors_out.append(
                {
                    "sensor_id": pm25.get("id"),
                    "parameter_name": "pm25",
                    "location_id": loc.get("id"),
                    "location_name": loc.get("name"),
                    "latitude": lat,
                    "longitude": lon,
                }
            )

    return sensors_out


def fetch_all_measurements(session: requests.Session, sensor_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch ALL measurements for a sensor from FROM_DATE onward, handling pagination.
    Returns:
      - list of measurements on success
      - [] if no results
      - None if the API times out with 408 (skip sensor)
    """
    headers = {"X-API-Key": API_KEY}
    page = 1
    all_meas: List[Dict[str, Any]] = []

    while True:
        params = {
            "datetime_from": FROM_DATE,
            "limit": MEASUREMENTS_LIMIT,
            "page": page,
        }

        data = request_json(
            session,
            f"{BASE_URL}/sensors/{sensor_id}/measurements",
            headers,
            params,
            return_none_on_408=True,
        )

        # 408 timeout -> skip the entire sensor
        if data is None:
            return None

        results = (data or {}).get("results", [])
        if not results:
            break

        all_meas.extend(results)

        meta = (data or {}).get("meta", {})
        total_pages = meta.get("totalPages") or meta.get("total_pages")
        if isinstance(total_pages, int) and page >= total_pages:
            break
        if len(results) < MEASUREMENTS_LIMIT:
            break

        page += 1
        time.sleep(SLEEP_S)

    return all_meas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output JSON filename")
    parser.add_argument("--start", type=int, required=True, help="Start index (1-based, inclusive)")
    parser.add_argument("--end", type=int, required=True, help="End index (1-based, inclusive)")
    args = parser.parse_args()

    if args.start < 1 or args.end < args.start:
        raise SystemExit("Invalid range. Use --start >= 1 and --end >= --start")

    kept = 0
    skipped_no_data = 0
    skipped_timeout = 0

    with requests.Session() as session:
        locations = fetch_locations(session)
        sensors = collect_sensors(locations)

        total = len(sensors)
        start0 = args.start - 1
        end0 = min(args.end, total)  # args.end is inclusive; slice end is exclusive

        subset = sensors[start0:end0]

        print(f"Total sensors: {total}")
        print(f"Processing sensors {args.start}..{min(args.end, total)}")

        output: List[Dict[str, Any]] = []

        for idx, s in enumerate(subset, start=args.start):
            sensor_id = s["sensor_id"]

            try:
                meas = fetch_all_measurements(session, sensor_id)
            except requests.HTTPError as e:
                # Any other HTTP error: skip and continue
                skipped_timeout += 1
                print(f"[{idx}] sensor {sensor_id} -> ERROR ({e}) (SKIPPED)")
                continue

            # 408 timeout handled -> meas is None
            if meas is None:
                skipped_timeout += 1
                print(f"[{idx}] sensor {sensor_id} -> TIMEOUT 408 (SKIPPED)")
                continue

            if len(meas) == 0:
                skipped_no_data += 1
                print(f"[{idx}] sensor {sensor_id} -> 0 measurements (SKIPPED)")
                continue

            entry = dict(s)
            entry["measurements_from"] = FROM_DATE
            entry["measurements_count"] = len(meas)
            entry["measurements"] = meas
            output.append(entry)

            kept += 1
            print(f"[{idx}] sensor {sensor_id} -> {len(meas)} measurements (KEPT)")

            time.sleep(SLEEP_S)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nFinished range.")
    print(f"Sensors kept: {kept}")
    print(f"Sensors skipped (no data): {skipped_no_data}")
    print(f"Sensors skipped (timeout/error): {skipped_timeout}")
    print(f"Wrote {len(output)} sensors to {args.out}")


if __name__ == "__main__":
    main()