from __future__ import annotations

import csv
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_PHASE6_INPUT_CSV = "iteration1/output/dataset/image_features_final.csv"
DEFAULT_PCA_OUTPUT_DIR = "iteration1/output/analysis/pca"
DEFAULT_PCA_SCORES_INPUT_CSV = "iteration1/output/analysis/pca/pca_scores_retained.csv"
DEFAULT_FEATURE_SPACES = ["selected_features", "pca_scores"]
NON_FEATURE_COLUMNS = {
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
    "record_pollution_level",
    "official_pm10",
    "official_pm25",
    "official_fetched_at",
    "zero_particle_flag",
    "manual_qc_flag",
    "analysis_success",
    "segmentation_success",
    "image_path",
    "roi_detected",
    "roi_width_px",
    "roi_height_px",
    "segmentation_method",
    "device_type",
    "sensor_exposure_time",
    "paper_type",
    "camera_type",
    "magnification",
    "weather_context",
    "failure_reason",
}
BENCHMARK_COLUMNS = [
    "candidate_id",
    "feature_space",
    "method",
    "method_variant",
    "k",
    "covariance_type",
    "min_cluster_size",
    "min_samples",
    "random_seed",
    "num_clusters",
    "noise_points",
    "noise_fraction",
    "smallest_cluster_fraction",
    "largest_cluster_fraction",
    "tiny_cluster_flag",
    "silhouette_score",
    "calinski_harabasz_score",
    "davies_bouldin_score",
    "bic",
    "aic",
    "fuzzy_partition_coefficient",
    "partition_entropy",
    "repeat_mean_ari",
    "repeat_std_ari",
    "bootstrap_mean_ari",
    "bootstrap_std_ari",
    "cluster_size_distribution",
]


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def spec_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def csv_ready_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return value
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_ready_value(row.get(field)) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_csv_list(raw_value: str) -> list[str]:
    values = [part.strip() for part in raw_value.split(",")]
    return [value for value in values if value]


def parse_k_values(raw_value: str) -> list[int]:
    values = []
    for item in parse_csv_list(raw_value):
        parsed = int(item)
        if parsed < 2:
            raise ValueError("All k values must be >= 2")
        values.append(parsed)
    if not values:
        raise ValueError("At least one k value is required")
    return sorted(set(values))


def load_feature_dataset(path: Path, non_feature_columns: set[str] | None = None) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    effective_non_feature_columns = non_feature_columns or NON_FEATURE_COLUMNS
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        rows = list(reader)

    if not rows:
        raise RuntimeError(f"Input CSV is empty: {path}")

    feature_columns = [column for column in headers if column not in effective_non_feature_columns]
    if not feature_columns:
        raise RuntimeError(f"No feature columns were found in the input CSV: {path}")

    metadata_rows: list[dict[str, Any]] = []
    matrix = np.empty((len(rows), len(feature_columns)), dtype=np.float64)

    for row_index, row in enumerate(rows):
        metadata_rows.append({column: row.get(column, "") for column in headers if column not in feature_columns})
        for column_index, column in enumerate(feature_columns):
            raw_value = row.get(column, "")
            if raw_value in ("", None):
                image_id = row.get("image_id") or f"row_{row_index}"
                raise RuntimeError(f"Missing numeric feature value for image {image_id}: {column}")
            try:
                matrix[row_index, column_index] = float(raw_value)
            except ValueError as error:
                image_id = row.get("image_id") or f"row_{row_index}"
                raise RuntimeError(
                    f"Could not parse numeric feature value for image {image_id}: {column}={raw_value!r}"
                ) from error

    return {
        "path": str(path),
        "headers": headers,
        "metadata_rows": metadata_rows,
        "feature_columns": feature_columns,
        "matrix": matrix,
    }


def load_phase6_dataset(path: Path) -> dict[str, Any]:
    return load_feature_dataset(path, non_feature_columns=NON_FEATURE_COLUMNS)


def load_pca_scores_dataset(path: Path) -> dict[str, Any]:
    return load_feature_dataset(path, non_feature_columns=NON_FEATURE_COLUMNS)


def align_feature_space_datasets(
    datasets: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray], dict[str, list[str]]]:
    if not datasets:
        raise RuntimeError("At least one feature-space dataset is required")

    if len(datasets) == 1:
        space_name, dataset = next(iter(datasets.items()))
        return (
            dataset["metadata_rows"],
            {space_name: dataset["matrix"]},
            {space_name: dataset["feature_columns"]},
        )

    reference_space = "pca_scores" if "pca_scores" in datasets else next(iter(datasets))
    reference_dataset = datasets[reference_space]
    lookups: dict[str, dict[str, int]] = {}

    for space_name, dataset in datasets.items():
        mapping: dict[str, int] = {}
        for row_index, metadata in enumerate(dataset["metadata_rows"]):
            image_id = metadata.get("image_id")
            if not image_id:
                raise RuntimeError(f"Missing image_id in {space_name} dataset row {row_index}")
            if image_id in mapping:
                raise RuntimeError(f"Duplicate image_id in {space_name} dataset: {image_id}")
            mapping[image_id] = row_index
        lookups[space_name] = mapping

    aligned_metadata_rows: list[dict[str, Any]] = []
    aligned_feature_rows: dict[str, list[np.ndarray]] = {space_name: [] for space_name in datasets}

    for metadata in reference_dataset["metadata_rows"]:
        image_id = metadata.get("image_id")
        missing_spaces = [space_name for space_name, mapping in lookups.items() if image_id not in mapping]
        if missing_spaces:
            missing_list = ", ".join(sorted(missing_spaces))
            raise RuntimeError(f"Image {image_id} is missing from aligned feature spaces: {missing_list}")
        aligned_metadata_rows.append(dict(metadata))
        for space_name, dataset in datasets.items():
            row_index = lookups[space_name][image_id]
            aligned_feature_rows[space_name].append(dataset["matrix"][row_index, :])

    aligned_feature_space_map = {
        space_name: np.vstack(rows) if rows else np.empty((0, 0), dtype=np.float64)
        for space_name, rows in aligned_feature_rows.items()
    }
    feature_columns_by_space = {
        space_name: dataset["feature_columns"]
        for space_name, dataset in datasets.items()
    }

    return aligned_metadata_rows, aligned_feature_space_map, feature_columns_by_space


def sample_feature_spaces(
    metadata_rows: list[dict[str, Any]],
    feature_space_map: dict[str, np.ndarray],
    sample_size: int,
    random_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray], list[int]]:
    total_rows = len(metadata_rows)
    if sample_size <= 0 or sample_size >= total_rows:
        return metadata_rows, feature_space_map, list(range(total_rows))

    rng = np.random.default_rng(random_seed)
    selected_indices = sorted(rng.choice(total_rows, size=sample_size, replace=False).tolist())
    sampled_metadata_rows = [metadata_rows[index] for index in selected_indices]
    sampled_feature_space_map = {
        space_name: matrix[selected_indices, :]
        for space_name, matrix in feature_space_map.items()
    }
    return sampled_metadata_rows, sampled_feature_space_map, selected_indices


def import_pyplot() -> Any | None:
    if not spec_available("matplotlib"):
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt
