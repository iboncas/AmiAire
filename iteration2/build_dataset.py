#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from dotenv import load_dotenv

try:
    import cv2
except ImportError:
    cv2 = None

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3001")
STANDARDIZED_ROI_SIZE = (1000, 1000)
REPO_ROOT = Path(__file__).resolve().parents[1]
COLOR_FEATURE_COLUMNS = [
    "roi_b_mean",
    "roi_b_std",
    "roi_g_mean",
    "roi_g_std",
    "roi_r_mean",
    "roi_r_std",
    "roi_h_mean",
    "roi_h_std",
    "roi_s_mean",
    "roi_s_std",
    "roi_v_mean",
    "roi_v_std",
    "roi_lab_l_mean",
    "roi_lab_l_std",
    "roi_lab_a_mean",
    "roi_lab_a_std",
    "roi_lab_b_mean",
    "roi_lab_b_std",
    "colorfulness",
    "particle_mask_mean_rgb_contrast",
    "particle_mask_mean_v_contrast",
]
PLACES_NUMERIC_COLUMNS = [
    "total",
    "transit",
    "park",
    "gas_station",
    "parking",
    "industrial",
    "major_road_proxy",
    "place_diversity_entropy",
    "green_vs_traffic_ratio_500m",
]
PLACES_CATEGORICAL_COLUMNS = [
    "dominant_place_category",
]
PLACES_ALL_COLUMNS = PLACES_NUMERIC_COLUMNS + PLACES_CATEGORICAL_COLUMNS
SENSOR_FIELDS = [
    "id",
    "ubicacion.latitud",
    "ubicacion.longitud",
    "fechaInicio",
    "fechaRecogida",
    "imagen",
    "metricas.pm10",
    "metricas.pm25",
    "nivelPolucion",
]
EXTENDED_FEATURE_SET_FALLBACK = [
    "num_particles",
    "area_percentage",
    "particle_density",
    "mean_pixel_intensity",
    "std_pixel_intensity",
    "orientation_entropy",
    "circular_variance",
    "area_median",
    "area_iqr",
    "area_p90",
    "solidity_median",
    "solidity_iqr",
    "aspect_ratio_median",
    "aspect_ratio_iqr",
    "feret_median",
    "feret_p90",
    "equivalent_diameter_median",
    "equivalent_diameter_p90",
    "circularity_median",
    "mean_intensity_median",
    "area_p25",
    "area_p75",
    "area_mean",
    "area_std",
    "solidity_p25",
    "solidity_p75",
    "solidity_p90",
    "solidity_mean",
    "solidity_std",
    "aspect_ratio_p25",
    "aspect_ratio_p75",
    "aspect_ratio_p90",
    "aspect_ratio_mean",
    "aspect_ratio_std",
    "feret_iqr",
    "feret_p25",
    "feret_p75",
    "feret_mean",
    "feret_std",
    "equivalent_diameter_iqr",
    "equivalent_diameter_p25",
    "equivalent_diameter_p75",
    "equivalent_diameter_mean",
    "equivalent_diameter_std",
    "eccentricity_median",
    "eccentricity_iqr",
    "eccentricity_p25",
    "eccentricity_p75",
    "eccentricity_p90",
    "eccentricity_mean",
    "eccentricity_std",
    "circularity_iqr",
    "circularity_p25",
    "circularity_p75",
    "circularity_p90",
    "circularity_mean",
    "circularity_std",
    "mean_intensity_iqr",
    "mean_intensity_p25",
    "mean_intensity_p75",
    "mean_intensity_p90",
    "mean_intensity_mean",
    "mean_intensity_std",
    "roi_b_mean",
    "roi_b_std",
    "roi_g_mean",
    "roi_g_std",
    "roi_r_mean",
    "roi_r_std",
    "roi_h_mean",
    "roi_h_std",
    "roi_s_mean",
    "roi_s_std",
    "roi_v_mean",
    "roi_v_std",
    "roi_lab_l_mean",
    "roi_lab_l_std",
    "roi_lab_a_mean",
    "roi_lab_a_std",
    "roi_lab_b_mean",
    "roi_lab_b_std",
    "colorfulness",
    "particle_mask_mean_rgb_contrast",
    "particle_mask_mean_v_contrast",
    "total",
    "transit",
    "park",
    "gas_station",
    "parking",
    "industrial",
    "major_road_proxy",
    "place_diversity_entropy",
    "green_vs_traffic_ratio_500m",
    "capture_month_sin",
    "capture_month_cos",
    "season_winter",
    "season_spring",
    "season_summer",
    "season_autumn",
]
PHASE6_DEFAULT_FALLBACK = [
    "num_particles",
    "area_percentage",
    "particle_density",
    "mean_pixel_intensity",
    "std_pixel_intensity",
    "orientation_entropy",
    "circular_variance",
    "area_median",
    "area_iqr",
    "area_p90",
    "solidity_median",
    "solidity_iqr",
    "solidity_p90",
    "aspect_ratio_median",
    "aspect_ratio_iqr",
    "aspect_ratio_p90",
    "feret_median",
    "feret_iqr",
    "feret_p90",
    "equivalent_diameter_median",
    "equivalent_diameter_iqr",
    "equivalent_diameter_p90",
    "eccentricity_median",
    "eccentricity_iqr",
    "eccentricity_p90",
    "circularity_median",
    "circularity_iqr",
    "circularity_p90",
    "mean_intensity_median",
    "mean_intensity_iqr",
    "mean_intensity_p90",
    "roi_s_mean",
    "roi_s_std",
    "roi_v_mean",
    "roi_v_std",
    "roi_lab_l_mean",
    "roi_lab_l_std",
    "roi_lab_b_mean",
    "roi_lab_b_std",
    "colorfulness",
    "particle_mask_mean_rgb_contrast",
    "particle_mask_mean_v_contrast",
    "total",
    "transit",
    "park",
    "gas_station",
    "parking",
    "industrial",
    "major_road_proxy",
    "place_diversity_entropy",
    "green_vs_traffic_ratio_500m",
    "capture_month_sin",
    "capture_month_cos",
    "season_winter",
    "season_spring",
    "season_summer",
    "season_autumn",
]
METADATA_COLUMNS = [
    "image_id",
    "sensor_id",
    "capture_datetime",
    "collection_datetime",
    "latitude",
    "longitude",
    "image_path",
    "roi_detected",
    "roi_width_px",
    "roi_height_px",
    "segmentation_method",
    "analysis_success",
    "segmentation_success",
    "manual_qc_flag",
    "device_type",
    "sensor_exposure_time",
    "paper_type",
    "camera_type",
    "magnification",
    "weather_context",
    "official_station_id",
    "roi_grid_label",
    "roi_grid_score",
    "roi_grid_confidence",
    "roi_grid_needs_review",
    "failure_reason",
]
CONTEXT_COLUMNS = [
    "record_pm10",
    "record_pm25",
    "record_pollution_level",
    "official_station_name",
    "official_station_distance_km",
    "official_pm10",
    "official_pm25",
    "official_fetched_at",
]
ID_COLUMNS = [
    "image_id",
    "sensor_id",
    "capture_datetime",
    "collection_datetime",
    "latitude",
    "longitude",
    "official_station_id",
    "official_station_name",
    "official_station_distance_km",
    "record_pm10",
    "record_pm25",
    "official_pm10",
    "official_pm25",
    "zero_particle_flag",
]
GLOBAL_NUMERIC_COLUMNS = [
    "roi_area_px",
    "num_particles",
    "area_percentage",
    "particle_density",
    "mean_pixel_intensity",
    "std_pixel_intensity",
    "blur_score_laplacian",
    "orientation_entropy",
    "circular_variance",
    "roi_b_mean",
    "roi_b_std",
    "roi_g_mean",
    "roi_g_std",
    "roi_r_mean",
    "roi_r_std",
    "roi_h_mean",
    "roi_h_std",
    "roi_s_mean",
    "roi_s_std",
    "roi_v_mean",
    "roi_v_std",
    "roi_lab_l_mean",
    "roi_lab_l_std",
    "roi_lab_a_mean",
    "roi_lab_a_std",
    "roi_lab_b_mean",
    "roi_lab_b_std",
    "colorfulness",
    "particle_mask_mean_rgb_contrast",
    "particle_mask_mean_v_contrast",
    "roi_grid_inner_margin_ratio",
    "roi_grid_inner_dark_ratio",
    "roi_grid_horizontal_line_count",
    "roi_grid_vertical_line_count",
    "roi_grid_horizontal_coverage",
    "roi_grid_vertical_coverage",
    "roi_grid_row_peak_count",
    "roi_grid_col_peak_count",
    "roi_grid_spacing_regularity",
    "total",
    "transit",
    "park",
    "gas_station",
    "parking",
    "industrial",
    "major_road_proxy",
    "place_diversity_entropy",
    "green_vs_traffic_ratio_500m",
]
TEMPORAL_ENRICHED_COLUMNS = [
    "capture_month",
    "capture_season",
    "capture_month_sin",
    "capture_month_cos",
    "season_winter",
    "season_spring",
    "season_summer",
    "season_autumn",
]
PHASE6_PRIORITY = {name: index for index, name in enumerate(PHASE6_DEFAULT_FALLBACK)}
SIZE_LOG_PREFIXES = (
    "num_particles",
    "particle_density",
    "area_",
    "feret_",
    "equivalent_diameter_",
)
SUFFIX_TO_GROUP = {
    "median": "central",
    "mean": "central",
    "iqr": "dispersion",
    "std": "dispersion",
    "p90": "upper",
    "p75": "upper_fallback",
    "p25": "lower",
}


def load_environment() -> None:
    root_env = REPO_ROOT / ".env"
    backend_env = REPO_ROOT / "backend" / ".env"
    load_dotenv(root_env)
    load_dotenv(backend_env, override=False)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def to_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def to_bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def nested_get(obj: dict[str, Any], path: str, default: Any = None) -> Any:
    current = obj
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def parse_capture_datetime(raw_value: Any) -> datetime | None:
    if not isinstance(raw_value, str):
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    normalized = cleaned.replace("Z", "+00:00")
    for candidate in (normalized, cleaned):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    try:
        return datetime.strptime(cleaned[:10], "%Y-%m-%d")
    except ValueError:
        return None


def season_for_month(month: int | None) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return ""


def derive_temporal_features(capture_datetime: Any) -> dict[str, Any]:
    parsed = parse_capture_datetime(capture_datetime)
    if parsed is None:
        return {
            "capture_month": None,
            "capture_season": "",
            "capture_month_sin": None,
            "capture_month_cos": None,
            "season_winter": None,
            "season_spring": None,
            "season_summer": None,
            "season_autumn": None,
        }

    month = parsed.month
    angle = (2.0 * math.pi * (month - 1)) / 12.0
    season = season_for_month(month)
    return {
        "capture_month": month,
        "capture_season": season,
        "capture_month_sin": float(math.sin(angle)),
        "capture_month_cos": float(math.cos(angle)),
        "season_winter": 1.0 if season == "winter" else 0.0,
        "season_spring": 1.0 if season == "spring" else 0.0,
        "season_summer": 1.0 if season == "summer" else 0.0,
        "season_autumn": 1.0 if season == "autumn" else 0.0,
    }


def enrich_image_feature_row(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    enriched.update(derive_temporal_features(row.get("capture_datetime")))
    return enriched


def decode_base64_image(image_b64: str | None, flags: int):
    if cv2 is None or not image_b64 or not isinstance(image_b64, str):
        return None
    payload = image_b64.split(",", 1)[1] if "," in image_b64 and image_b64.startswith("data:") else image_b64
    try:
        image_bytes = base64.b64decode(payload)
    except Exception:
        return None
    np_data = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(np_data, flags)


def _mean_and_std(values: np.ndarray) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    return float(np.mean(array)), float(np.std(array))


def compute_color_features_from_encoded_roi(
    roi_image_b64: str | None,
    binary_mask_b64: str | None,
) -> dict[str, Any]:
    color_features = {column: None for column in COLOR_FEATURE_COLUMNS}
    roi_bgr = decode_base64_image(roi_image_b64, cv2.IMREAD_COLOR) if cv2 is not None else None
    if roi_bgr is None:
        return color_features

    standardized_bgr = cv2.resize(roi_bgr, STANDARDIZED_ROI_SIZE, interpolation=cv2.INTER_CUBIC)
    bgr_float = standardized_bgr.astype(np.float64)

    for channel_name, channel_index in (("b", 0), ("g", 1), ("r", 2)):
        mean_value, std_value = _mean_and_std(bgr_float[:, :, channel_index])
        color_features[f"roi_{channel_name}_mean"] = mean_value
        color_features[f"roi_{channel_name}_std"] = std_value

    hsv = cv2.cvtColor(standardized_bgr, cv2.COLOR_BGR2HSV).astype(np.float64)
    for channel_name, channel_index in (("h", 0), ("s", 1), ("v", 2)):
        mean_value, std_value = _mean_and_std(hsv[:, :, channel_index])
        color_features[f"roi_{channel_name}_mean"] = mean_value
        color_features[f"roi_{channel_name}_std"] = std_value

    lab = cv2.cvtColor(standardized_bgr, cv2.COLOR_BGR2LAB).astype(np.float64)
    for channel_name, channel_index in (("l", 0), ("a", 1), ("b", 2)):
        mean_value, std_value = _mean_and_std(lab[:, :, channel_index])
        color_features[f"roi_lab_{channel_name}_mean"] = mean_value
        color_features[f"roi_lab_{channel_name}_std"] = std_value

    red = bgr_float[:, :, 2]
    green = bgr_float[:, :, 1]
    blue = bgr_float[:, :, 0]
    rg = red - green
    yb = (0.5 * (red + green)) - blue
    color_features["colorfulness"] = float(
        np.sqrt(np.std(rg) ** 2 + np.std(yb) ** 2) + 0.3 * np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2)
    )

    mask = decode_base64_image(binary_mask_b64, cv2.IMREAD_GRAYSCALE) if cv2 is not None else None
    if mask is None:
        return color_features
    standardized_mask = cv2.resize(mask, STANDARDIZED_ROI_SIZE, interpolation=cv2.INTER_NEAREST) > 0
    inverse_mask = ~standardized_mask
    if not np.any(standardized_mask) or not np.any(inverse_mask):
        return color_features

    particle_pixels = bgr_float[standardized_mask]
    background_pixels = bgr_float[inverse_mask]
    particle_mean_bgr = np.mean(particle_pixels, axis=0)
    background_mean_bgr = np.mean(background_pixels, axis=0)
    color_features["particle_mask_mean_rgb_contrast"] = float(
        np.mean(np.abs(particle_mean_bgr - background_mean_bgr))
    )

    hsv_v = hsv[:, :, 2]
    color_features["particle_mask_mean_v_contrast"] = float(
        abs(np.mean(hsv_v[standardized_mask]) - np.mean(hsv_v[inverse_mask]))
    )

    return color_features


def merge_feature_lists(primary: list[str] | None, fallback: list[str]) -> list[str]:
    merged = []
    seen = set()
    for column in (primary or []) + fallback:
        if column not in seen:
            merged.append(column)
            seen.add(column)
    return merged


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def load_places_features(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    places_by_id: dict[str, dict[str, Any]] = {}
    for row in load_csv_rows(path):
        row_id = (row.get("sensor_id") or row.get("image_id") or "").strip()
        if not row_id:
            continue

        normalized: dict[str, Any] = {}
        for column in PLACES_NUMERIC_COLUMNS:
            normalized[column] = to_float_or_none(row.get(column))
        for column in PLACES_CATEGORICAL_COLUMNS:
            normalized[column] = row.get(column) or ""
        places_by_id[row_id] = normalized
    return places_by_id


def merge_places_into_feature_row(
    feature_row: dict[str, Any],
    places_row: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(feature_row)
    if places_row is None:
        for column in PLACES_NUMERIC_COLUMNS:
            merged.setdefault(column, None)
        for column in PLACES_CATEGORICAL_COLUMNS:
            merged.setdefault(column, "")
        return merged

    for column in PLACES_NUMERIC_COLUMNS:
        merged[column] = places_row.get(column)
    for column in PLACES_CATEGORICAL_COLUMNS:
        merged[column] = places_row.get(column) or ""
    return merged


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return response.status, parsed
    except HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"success": False, "error": body[:500]}
        return error.code, parsed
    except URLError as error:
        raise RuntimeError(f"Request failed for {url}: {error}") from error


def fetch_sensors(base_url: str) -> list[dict[str, Any]]:
    query = urlencode({"fields": ",".join(SENSOR_FIELDS)})
    status, payload = request_json("GET", f"{base_url}/api/sensores?{query}", timeout=60)
    if status != 200 or not payload.get("success"):
        raise RuntimeError(f"Could not load sensors from backend ({status}): {payload}")
    data = payload.get("data")
    return data if isinstance(data, list) else []


def load_official_stations_fallback() -> list[dict[str, Any]]:
    path = REPO_ROOT / "backend" / "src" / "data" / "stations_coordinates.csv"
    if not path.exists():
        return []

    stations = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lat = to_float_or_none(row.get("latitude"))
            lon = to_float_or_none(row.get("longitude"))
            station_id = row.get("gml_id")
            name = row.get("name")
            if not station_id or not name or lat is None or lon is None:
                continue
            stations.append(
                {
                    "id": station_id,
                    "nombre": name,
                    "ubicacion": {"latitud": lat, "longitud": lon},
                    "metricas": {"pm10": None, "pm25": None},
                    "fechaRecogida": "",
                }
            )
    return stations


def fetch_official_stations(base_url: str) -> list[dict[str, Any]]:
    status, payload = request_json("GET", f"{base_url}/api/estaciones-oficiales", timeout=60)
    if status == 200 and payload.get("success") and isinstance(payload.get("data"), list):
        stations = payload["data"]
        if stations:
            return stations
    return load_official_stations_fallback()


def fetch_images(base_url: str, ids: list[str], timeout: int = 120) -> dict[str, str]:
    if not ids:
        return {}
    status, payload = request_json(
        "POST",
        f"{base_url}/api/imagenes",
        payload={"ids": ids},
        timeout=timeout,
    )
    if status != 200 or not isinstance(payload, list):
        raise RuntimeError(f"Could not load images batch ({status}): {payload}")

    out: dict[str, str] = {}
    for item in payload:
        image_id = item.get("id")
        base64_value = item.get("base64")
        if isinstance(image_id, str) and isinstance(base64_value, str):
            out[image_id] = base64_value
    return out


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * radius_km * math.asin(math.sqrt(a))


def find_nearest_station(lat: float | None, lon: float | None, stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if lat is None or lon is None:
        return None

    nearest = None
    best_distance = None
    for station in stations:
        station_lat = to_float_or_none(nested_get(station, "ubicacion.latitud"))
        station_lon = to_float_or_none(nested_get(station, "ubicacion.longitud"))
        if station_lat is None or station_lon is None:
            continue
        distance = haversine_km(lat, lon, station_lat, station_lon)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            nearest = {
                "id": station.get("id"),
                "name": station.get("nombre"),
                "distance_km": distance,
                "pm10": to_float_or_none(nested_get(station, "metricas.pm10")),
                "pm25": to_float_or_none(nested_get(station, "metricas.pm25")),
                "fetched_at": station.get("fechaRecogida") or "",
            }
    return nearest


def build_metadata(sensor: dict[str, Any], nearest_station: dict[str, Any] | None) -> dict[str, Any]:
    lat = to_float_or_none(nested_get(sensor, "ubicacion.latitud"))
    lon = to_float_or_none(nested_get(sensor, "ubicacion.longitud"))
    return {
        "image_id": sensor.get("id"),
        "sensor_id": sensor.get("id"),
        "capture_datetime": sensor.get("fechaInicio") or "",
        "collection_datetime": sensor.get("fechaRecogida") or "",
        "latitude": lat,
        "longitude": lon,
        "image_path": sensor.get("imagen") or "",
        "official_station_id": nearest_station.get("id") if nearest_station else "",
    }


def build_context(sensor: dict[str, Any], nearest_station: dict[str, Any] | None) -> dict[str, Any]:
    context = {
        "record_pm10": to_float_or_none(nested_get(sensor, "metricas.pm10")),
        "record_pm25": to_float_or_none(nested_get(sensor, "metricas.pm25")),
        "record_pollution_level": sensor.get("nivelPolucion") or "",
    }
    if nearest_station:
        context.update(
            {
                "official_station_name": nearest_station.get("name") or "",
                "official_station_distance_km": nearest_station.get("distance_km"),
                "official_pm10": nearest_station.get("pm10"),
                "official_pm25": nearest_station.get("pm25"),
                "official_fetched_at": nearest_station.get("fetched_at") or "",
            }
        )
    return context


def build_empty_result(metadata: dict[str, Any], context: dict[str, Any], failure_reason: str) -> dict[str, Any]:
    metadata_row = {column: metadata.get(column) for column in METADATA_COLUMNS}
    metadata_row.update(
        {
            "roi_detected": False,
            "roi_width_px": None,
            "roi_height_px": None,
            "segmentation_method": "",
            "analysis_success": False,
            "segmentation_success": False,
            "manual_qc_flag": "pending",
            "failure_reason": failure_reason,
        }
    )

    feature_row = dict(metadata_row)
    feature_row.update({column: context.get(column) for column in CONTEXT_COLUMNS})
    feature_row.update({column: None for column in GLOBAL_NUMERIC_COLUMNS})
    feature_row.update({column: None for column in COLOR_FEATURE_COLUMNS})
    feature_row["zero_particle_flag"] = None

    for feature_name in EXTENDED_FEATURE_SET_FALLBACK:
        feature_row.setdefault(feature_name, None)

    return {
        "images_metadata": metadata_row,
        "particles": [],
        "image_features": feature_row,
        "feature_sets": {
            "core": [],
            "extended": EXTENDED_FEATURE_SET_FALLBACK,
            "phase6_default": PHASE6_DEFAULT_FALLBACK,
        },
    }


def extract_dataset_outputs(response_payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(response_payload, dict):
        return None
    if response_payload.get("success"):
        data = response_payload.get("data")
        if isinstance(data, dict):
            return data.get("datasetOutputs")
        return None
    return response_payload.get("datasetOutputs")


def process_sensor_record(
    base_url: str,
    sensor: dict[str, Any],
    nearest_station: dict[str, Any] | None,
    model_type: str,
    image_b64: str | None,
) -> tuple[dict[str, Any], str]:
    metadata = build_metadata(sensor, nearest_station)
    context = build_context(sensor, nearest_station)

    if not image_b64:
        return build_empty_result(metadata, context, "image_not_available"), "image_not_available"

    status, payload = request_json(
        "POST",
        f"{base_url}/api/analysis/process",
        payload={
            "imageB64": image_b64,
            "modelType": model_type,
            "metadata": metadata,
            "contextualData": context,
        },
        timeout=180,
    )

    dataset_outputs = extract_dataset_outputs(payload)
    if dataset_outputs:
        failure_reason = nested_get(dataset_outputs, "images_metadata.failure_reason")
        if status == 200:
            image_features = dataset_outputs.get("image_features") or {}
            roi_image_b64 = (
                nested_get(payload, "data.roiImageB64")
                or nested_get(payload, "data.roi_image_b64")
                or payload.get("roiImageB64")
                or payload.get("roi_image_b64")
            )
            binary_mask_b64 = (
                nested_get(payload, "data.binaryB64")
                or nested_get(payload, "data.binary_b64")
                or payload.get("binaryB64")
                or payload.get("binary_b64")
            )
            image_features.update(
                compute_color_features_from_encoded_roi(
                    roi_image_b64,
                    binary_mask_b64,
                )
            )
            dataset_outputs["image_features"] = image_features
            return dataset_outputs, "success"
        if isinstance(failure_reason, str) and failure_reason:
            return dataset_outputs, failure_reason
        return dataset_outputs, "analysis_failed"

    error_label = "analysis_failed" if status >= 400 else "unknown_failure"
    if isinstance(payload, dict) and payload.get("error"):
        error_label = str(payload["error"])
    return build_empty_result(metadata, context, error_label), error_label


def csv_ready_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], preferred_columns: list[str] | None = None) -> list[str]:
    preferred_columns = preferred_columns or []
    deduped_preferred = []
    preferred_seen = set()
    for column in preferred_columns:
        if column not in preferred_seen:
            deduped_preferred.append(column)
            preferred_seen.add(column)

    discovered = []
    discovered_set = set()
    for row in rows:
        for key in row.keys():
            if key not in discovered_set and key not in deduped_preferred:
                discovered.append(key)
                discovered_set.add(key)

    columns = [column for column in deduped_preferred if any(column in row for row in rows)] + discovered

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_ready_value(row.get(column)) for column in columns})
    return columns


def finite_mask(values: np.ndarray) -> np.ndarray:
    return np.isfinite(values)


def sample_skewness(values: np.ndarray) -> float:
    if values.size < 3:
        return 0.0
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0.0:
        return 0.0
    centered = (values - mean) / std
    return float(np.mean(centered ** 3))


def rankdata_average(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    ranks = np.empty(values.shape[0], dtype=np.float64)
    start = 0
    while start < sorted_values.shape[0]:
        end = start + 1
        while end < sorted_values.shape[0] and sorted_values[end] == sorted_values[start]:
            end += 1
        average_rank = ((start + end - 1) / 2.0) + 1.0
        ranks[order[start:end]] = average_rank
        start = end
    return ranks


def spearman_corrcoef(matrix: np.ndarray) -> np.ndarray:
    if matrix.shape[1] == 0:
        return np.empty((0, 0), dtype=np.float64)

    ranked = np.empty_like(matrix, dtype=np.float64)
    for index in range(matrix.shape[1]):
        ranked[:, index] = rankdata_average(matrix[:, index])
    corr = np.corrcoef(ranked, rowvar=False)
    return np.nan_to_num(corr, nan=0.0)


def is_log_eligible(column: str) -> bool:
    return any(column == prefix or column.startswith(prefix) for prefix in SIZE_LOG_PREFIXES)


def split_family_and_suffix(column: str) -> tuple[str | None, str | None]:
    for suffix in ("median", "iqr", "p25", "p75", "p90", "mean", "std"):
        needle = f"_{suffix}"
        if column.endswith(needle):
            return column[: -len(needle)], suffix
    return None, None


def feature_priority(column: str) -> tuple[int, int, str]:
    if column in PHASE6_PRIORITY:
        return (0, PHASE6_PRIORITY[column], column)
    if column in EXTENDED_FEATURE_SET_FALLBACK:
        return (1, EXTENDED_FEATURE_SET_FALLBACK.index(column), column)
    return (2, 9999, column)


def preprocess_feature_rows(
    rows: list[dict[str, Any]],
    feature_sets: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], np.ndarray, list[str]]:
    eligible_rows = [
        row
        for row in rows
        if to_bool_or_none(row.get("roi_detected")) is True
        and to_bool_or_none(row.get("analysis_success")) is True
        and to_bool_or_none(row.get("segmentation_success")) is True
    ]

    extended_features = feature_sets.get("extended") or EXTENDED_FEATURE_SET_FALLBACK
    candidate_columns = [column for column in extended_features if any(column in row for row in eligible_rows)]
    if not eligible_rows or not candidate_columns:
        report = {
            "eligible_rows": len(eligible_rows),
            "preprocessed_feature_columns": [],
            "reduced_feature_columns": [],
            "removed_low_variance": [],
            "log1p_columns": [],
            "winsorized_columns": [],
            "imputed_columns": {},
            "correlation_threshold": 0.9,
            "scaling_method_by_column": {},
        }
        return [], [], report, np.empty((0, 0), dtype=np.float64), []

    matrix = np.full((len(eligible_rows), len(candidate_columns)), np.nan, dtype=np.float64)
    zero_particle_flags = np.array(
        [to_bool_or_none(row.get("zero_particle_flag")) is True for row in eligible_rows],
        dtype=bool,
    )

    for row_index, row in enumerate(eligible_rows):
        for column_index, column in enumerate(candidate_columns):
            matrix[row_index, column_index] = to_float_or_none(row.get(column)) if row.get(column) not in ("", None) else np.nan

    kept_columns = []
    kept_matrix_columns = []
    removed_low_variance = []
    imputed_columns: dict[str, str] = {}

    for column_index, column in enumerate(candidate_columns):
        column_values = matrix[:, column_index]
        finite = finite_mask(column_values)
        if not np.any(finite):
            removed_low_variance.append(column)
            continue

        finite_values = column_values[finite]
        if np.unique(np.round(finite_values, 12)).size <= 1:
            removed_low_variance.append(column)
            continue

        fill_value = float(np.median(finite_values))
        if np.any(~finite):
            if np.any(~finite & ~zero_particle_flags):
                imputed_columns[column] = "median"
            else:
                fill_value = 0.0
                imputed_columns[column] = "zero_for_zero_particle_rows"
            column_values = np.where(finite, column_values, fill_value)
        else:
            column_values = column_values.copy()

        if float(np.std(column_values)) < 1e-12:
            removed_low_variance.append(column)
            continue

        kept_columns.append(column)
        kept_matrix_columns.append(column_values)

    if not kept_columns:
        report = {
            "eligible_rows": len(eligible_rows),
            "preprocessed_feature_columns": [],
            "reduced_feature_columns": [],
            "removed_low_variance": removed_low_variance,
            "log1p_columns": [],
            "winsorized_columns": [],
            "imputed_columns": imputed_columns,
            "correlation_threshold": 0.9,
            "scaling_method_by_column": {},
        }
        return [], [], report, np.empty((0, 0), dtype=np.float64), []

    working_matrix = np.column_stack(kept_matrix_columns)

    winsorized_columns = []
    for column_index, column in enumerate(kept_columns):
        column_values = working_matrix[:, column_index]
        lower, upper = np.percentile(column_values, [1, 99])
        clipped = np.clip(column_values, lower, upper)
        if not np.allclose(clipped, column_values):
            winsorized_columns.append(column)
        working_matrix[:, column_index] = clipped

    log1p_columns = []
    for column_index, column in enumerate(kept_columns):
        column_values = working_matrix[:, column_index]
        if np.min(column_values) < 0:
            continue
        if is_log_eligible(column) and abs(sample_skewness(column_values)) > 1.0:
            working_matrix[:, column_index] = np.log1p(column_values)
            log1p_columns.append(column)

    scaled_matrix = np.empty_like(working_matrix, dtype=np.float64)
    scaling_method_by_column: dict[str, str] = {}
    for column_index, _column in enumerate(kept_columns):
        column_values = working_matrix[:, column_index]
        median = float(np.median(column_values))
        std = float(np.std(column_values))
        q25, q75 = np.percentile(column_values, [25, 75])
        scale = float(q75 - q25)
        scaling_method = "robust_iqr"
        if scale == 0.0:
            scale = std
            scaling_method = "std_zero_iqr"
        elif std > 0.0 and scale < (0.1 * std):
            # Prevent near-saturated features from exploding after robust scaling.
            scale = std
            scaling_method = "std_narrow_iqr"
        if scale == 0.0:
            scale = 1.0
            scaling_method = "unit_scale_zero_std"
        scaled_matrix[:, column_index] = (column_values - median) / scale
        scaling_method_by_column[kept_columns[column_index]] = scaling_method

    preprocessed_rows = []
    for row_index, row in enumerate(eligible_rows):
        output_row = {column: row.get(column) for column in ID_COLUMNS}
        output_row["manual_qc_flag"] = row.get("manual_qc_flag")
        output_row["analysis_success"] = row.get("analysis_success")
        output_row["segmentation_success"] = row.get("segmentation_success")
        for column_index, column in enumerate(kept_columns):
            output_row[column] = float(scaled_matrix[row_index, column_index])
        preprocessed_rows.append(output_row)

    report = {
        "eligible_rows": len(eligible_rows),
        "preprocessed_feature_columns": kept_columns,
        "removed_low_variance": removed_low_variance,
        "log1p_columns": log1p_columns,
        "winsorized_columns": winsorized_columns,
        "imputed_columns": imputed_columns,
        "correlation_threshold": 0.9,
        "scaling_method_by_column": scaling_method_by_column,
    }

    return preprocessed_rows, eligible_rows, report, scaled_matrix, kept_columns


def reduce_feature_rows(
    preprocessed_rows: list[dict[str, Any]],
    scaled_matrix: np.ndarray,
    kept_columns: list[str],
    feature_sets: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not preprocessed_rows or not kept_columns:
        return [], {
            "phase6_default_candidates": feature_sets.get("phase6_default") or PHASE6_DEFAULT_FALLBACK,
            "selected_columns": [],
            "removed_by_correlation": {},
            "removed_by_family_balance": {},
        }

    ordered_columns = sorted(kept_columns, key=feature_priority)
    ordered_indices = [kept_columns.index(column) for column in ordered_columns]
    ordered_matrix = scaled_matrix[:, ordered_indices]
    corr = spearman_corrcoef(ordered_matrix)

    selected_columns: list[str] = []
    removed_by_correlation: dict[str, str] = {}
    for column_index, column in enumerate(ordered_columns):
        if column in removed_by_correlation:
            continue
        selected_columns.append(column)
        for next_index in range(column_index + 1, len(ordered_columns)):
            candidate = ordered_columns[next_index]
            if candidate in removed_by_correlation:
                continue
            if abs(float(corr[column_index, next_index])) >= 0.90:
                removed_by_correlation[candidate] = column

    balanced_columns: list[str] = []
    selected_set = set(selected_columns)
    family_groups_used: set[tuple[str, str]] = set()
    removed_by_family_balance: dict[str, str] = {}
    phase6_default = feature_sets.get("phase6_default") or PHASE6_DEFAULT_FALLBACK

    for column in sorted(selected_set, key=feature_priority):
        if column not in selected_set:
            continue
        if column in phase6_default and column not in balanced_columns:
            family, suffix = split_family_and_suffix(column)
            group = SUFFIX_TO_GROUP.get(suffix) if suffix else None
            if family and group in {"central", "dispersion", "upper"}:
                key = (family, group)
                if key in family_groups_used:
                    removed_by_family_balance[column] = "phase6_default_duplicate"
                    continue
                family_groups_used.add(key)
            balanced_columns.append(column)

    for column in sorted(selected_columns, key=feature_priority):
        if column in balanced_columns:
            continue
        family, suffix = split_family_and_suffix(column)
        group = SUFFIX_TO_GROUP.get(suffix) if suffix else None
        if family and group in {"central", "dispersion", "upper"}:
            key = (family, group)
            if key in family_groups_used:
                removed_by_family_balance[column] = next(
                    kept
                    for kept in balanced_columns
                    if split_family_and_suffix(kept)[0] == family
                    and SUFFIX_TO_GROUP.get(split_family_and_suffix(kept)[1]) == group
                )
                continue
            family_groups_used.add(key)
            balanced_columns.append(column)
            continue
        if family and group in {"upper_fallback", "lower"}:
            removed_by_family_balance[column] = "family_balance_rule"
            continue
        balanced_columns.append(column)

    reduced_rows = []
    for row in preprocessed_rows:
        reduced = {column: row.get(column) for column in ID_COLUMNS}
        reduced["manual_qc_flag"] = row.get("manual_qc_flag")
        reduced["analysis_success"] = row.get("analysis_success")
        reduced["segmentation_success"] = row.get("segmentation_success")
        for column in balanced_columns:
            reduced[column] = row.get(column)
        reduced_rows.append(reduced)

    return reduced_rows, {
        "phase6_default_candidates": phase6_default,
        "selected_columns": balanced_columns,
        "removed_by_correlation": removed_by_correlation,
        "removed_by_family_balance": removed_by_family_balance,
    }


def main() -> None:
    load_environment()

    parser = argparse.ArgumentParser(
        description="Build dataset tables and cleaned feature matrices through phase 6."
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL),
        help="Backend base URL, for example http://localhost:3001",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration2/output/dataset",
        help="Directory where CSV and JSON outputs will be written",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of sensor records to process",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Optional number of sensor records to skip before processing",
    )
    parser.add_argument(
        "--image-batch-size",
        type=int,
        default=50,
        help="Number of images to fetch per /api/imagenes request",
    )
    parser.add_argument(
        "--model-type",
        default="PM10",
        choices=["PM10", "PM25"],
        help="Model type forwarded to the image analysis endpoint",
    )
    parser.add_argument(
        "--analysis-concurrency",
        type=int,
        default=6,
        help="Number of parallel /api/analysis/process requests per image batch",
    )
    args = parser.parse_args()

    if cv2 is None:
        print(
            "Warning: opencv-python is not installed. Color features will be left empty in this run.",
            flush=True,
        )

    output_dir = Path(args.output_dir).resolve()
    ensure_directory(output_dir)
    places_features_path = output_dir / "places_features.csv"
    places_by_id = load_places_features(places_features_path)
    places_merge_summary = {
        "places_features_path": str(places_features_path),
        "places_features_found": places_features_path.exists(),
        "places_rows_loaded": len(places_by_id),
        "matched_feature_rows": 0,
        "unmatched_feature_rows": 0,
    }

    sensors = fetch_sensors(args.backend_url)
    if args.offset > 0:
        sensors = sensors[args.offset :]
    if args.limit > 0:
        sensors = sensors[: args.limit]

    official_stations = fetch_official_stations(args.backend_url)

    images_metadata_rows: list[dict[str, Any]] = []
    particle_rows: list[dict[str, Any]] = []
    image_feature_rows: list[dict[str, Any]] = []
    feature_sets = {
        "core": [],
        "extended": EXTENDED_FEATURE_SET_FALLBACK,
        "phase6_default": PHASE6_DEFAULT_FALLBACK,
    }
    processing_summary = {
        "processed_records": 0,
        "successful_analyses": 0,
        "roi_failures": 0,
        "missing_images": 0,
        "other_failures": 0,
    }

    batch_size = max(1, args.image_batch_size)
    max_workers = max(1, args.analysis_concurrency)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for start in range(0, len(sensors), batch_size):
            batch = sensors[start : start + batch_size]
            batch_ids = [sensor.get("id") for sensor in batch if isinstance(sensor.get("id"), str)]
            images_by_id = fetch_images(args.backend_url, batch_ids) if batch_ids else {}

            batch_futures = []
            for index, sensor in enumerate(batch):
                sensor_id = sensor.get("id")
                lat = to_float_or_none(nested_get(sensor, "ubicacion.latitud"))
                lon = to_float_or_none(nested_get(sensor, "ubicacion.longitud"))
                nearest_station = find_nearest_station(lat, lon, official_stations)
                future = executor.submit(
                    process_sensor_record,
                    args.backend_url,
                    sensor,
                    nearest_station,
                    args.model_type,
                    images_by_id.get(sensor_id),
                )
                batch_futures.append((index, sensor, future))

            ordered_results = []
            for index, sensor, future in batch_futures:
                dataset_outputs, status_label = future.result()
                ordered_results.append((index, sensor, dataset_outputs, status_label))

            for _index, _sensor, dataset_outputs, status_label in sorted(ordered_results, key=lambda item: item[0]):
                images_metadata = dataset_outputs.get("images_metadata") or {}
                particles = dataset_outputs.get("particles") or []
                image_features = dataset_outputs.get("image_features") or {}
                returned_feature_sets = dataset_outputs.get("feature_sets") or {}
                places_key = (image_features.get("sensor_id") or image_features.get("image_id") or "").strip()
                places_row = places_by_id.get(places_key) if places_key else None
                image_features = merge_places_into_feature_row(image_features, places_row)

                images_metadata_rows.append(images_metadata)
                particle_rows.extend(particles)
                image_feature_rows.append(image_features)
                if places_row is not None:
                    places_merge_summary["matched_feature_rows"] += 1
                else:
                    places_merge_summary["unmatched_feature_rows"] += 1

                if returned_feature_sets.get("extended"):
                    feature_sets = returned_feature_sets

                processing_summary["processed_records"] += 1
                if status_label == "success":
                    processing_summary["successful_analyses"] += 1
                elif status_label == "image_not_available":
                    processing_summary["missing_images"] += 1
                elif status_label == "roi_not_detected":
                    processing_summary["roi_failures"] += 1
                else:
                    processing_summary["other_failures"] += 1

                if processing_summary["processed_records"] % 25 == 0:
                    print(
                        f"Processed {processing_summary['processed_records']}/{len(sensors)} records",
                        flush=True,
                    )

    image_feature_rows = [enrich_image_feature_row(row) for row in image_feature_rows]
    feature_sets = {
        "core": merge_feature_lists(feature_sets.get("core"), []),
        "extended": merge_feature_lists(feature_sets.get("extended"), EXTENDED_FEATURE_SET_FALLBACK),
        "phase6_default": merge_feature_lists(feature_sets.get("phase6_default"), PHASE6_DEFAULT_FALLBACK),
    }

    images_metadata_columns = write_csv(
        output_dir / "images_metadata.csv",
        images_metadata_rows,
        preferred_columns=METADATA_COLUMNS,
    )
    particle_columns = write_csv(
        output_dir / "particles.csv",
        particle_rows,
        preferred_columns=[
            "image_id",
            "particle_id",
            "area_px",
            "perimeter_px",
            "equivalent_diameter_px",
            "major_axis_length_px",
            "minor_axis_length_px",
            "aspect_ratio",
            "solidity",
            "eccentricity",
            "feret_diameter_max_px",
            "orientation_rad",
            "circularity",
            "mean_intensity",
            "std_intensity",
            "min_intensity",
            "max_intensity",
            "centroid_x",
            "centroid_y",
        ],
    )
    enriched_feature_columns = write_csv(
        output_dir / "image_features_enriched.csv",
        image_feature_rows,
        preferred_columns=METADATA_COLUMNS
        + CONTEXT_COLUMNS
        + TEMPORAL_ENRICHED_COLUMNS
        + PLACES_ALL_COLUMNS
        + EXTENDED_FEATURE_SET_FALLBACK,
    )

    preprocessed_rows, eligible_rows, preprocessing_report, scaled_matrix, kept_columns = preprocess_feature_rows(
        image_feature_rows,
        feature_sets,
    )
    preprocessed_columns = write_csv(
        output_dir / "image_features_preprocessed.csv",
        preprocessed_rows,
        preferred_columns=ID_COLUMNS + kept_columns,
    )
    reduced_rows, reduction_report = reduce_feature_rows(
        preprocessed_rows,
        scaled_matrix,
        kept_columns,
        feature_sets,
    )

    final_columns = write_csv(
        output_dir / "image_features_final.csv",
        reduced_rows,
        preferred_columns=ID_COLUMNS + reduction_report.get("selected_columns", []),
    )

    report = {
        "backend_url": args.backend_url,
        "output_dir": str(output_dir),
        "analysis_concurrency": max_workers,
        "image_batch_size": batch_size,
        "total_sensor_records": len(sensors),
        "processing_summary": processing_summary,
        "places_merge_summary": places_merge_summary,
        "official_station_count": len(official_stations),
        "feature_sets": feature_sets,
        "raw_output_files": {
            "images_metadata_csv": str(output_dir / "images_metadata.csv"),
            "particles_csv": str(output_dir / "particles.csv"),
            "image_features_enriched_csv": str(output_dir / "image_features_enriched.csv"),
            "image_features_preprocessed_csv": str(output_dir / "image_features_preprocessed.csv"),
        },
        "raw_output_columns": {
            "images_metadata_csv": images_metadata_columns,
            "particles_csv": particle_columns,
            "image_features_enriched_csv": enriched_feature_columns,
            "image_features_preprocessed_csv": preprocessed_columns,
        },
        "final_output_file": str(output_dir / "image_features_final.csv"),
        "final_output_columns": final_columns,
        "phase5": preprocessing_report,
        "phase6": reduction_report,
        "eligible_rows_for_phase5_and_phase6": len(eligible_rows),
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
