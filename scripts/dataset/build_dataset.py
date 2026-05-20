#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from dotenv import load_dotenv

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3001")
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
    "roi_grid_inner_margin_ratio",
    "roi_grid_inner_dark_ratio",
    "roi_grid_horizontal_line_count",
    "roi_grid_vertical_line_count",
    "roi_grid_horizontal_coverage",
    "roi_grid_vertical_coverage",
    "roi_grid_row_peak_count",
    "roi_grid_col_peak_count",
    "roi_grid_spacing_regularity",
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
    root_env = Path(__file__).resolve().parents[2] / ".env"
    backend_env = Path(__file__).resolve().parents[2] / "backend" / ".env"
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
    path = Path(__file__).resolve().parents[2] / "backend" / "src" / "data" / "stations_coordinates.csv"
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
        default="output/dataset",
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

    output_dir = Path(args.output_dir).resolve()
    ensure_directory(output_dir)

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

                images_metadata_rows.append(images_metadata)
                particle_rows.extend(particles)
                image_feature_rows.append(image_features)

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

    preprocessed_rows, eligible_rows, preprocessing_report, scaled_matrix, kept_columns = preprocess_feature_rows(
        image_feature_rows,
        feature_sets,
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
        "official_station_count": len(official_stations),
        "feature_sets": feature_sets,
        "final_output_file": str(output_dir / "image_features_final.csv"),
        "final_output_columns": final_columns,
        "phase5": preprocessing_report,
        "phase6": reduction_report,
        "eligible_rows_for_phase5_and_phase6": len(eligible_rows),
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
