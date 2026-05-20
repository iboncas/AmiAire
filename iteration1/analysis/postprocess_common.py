from __future__ import annotations

import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np

from common import NON_FEATURE_COLUMNS, import_pyplot, write_csv, write_json

METHOD_NAMES = ("kmeans", "ward", "gmm", "fuzzy", "hdbscan")
BENCHMARK_FLOAT_COLUMNS = {
    "noise_fraction",
    "smallest_cluster_fraction",
    "largest_cluster_fraction",
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
}
BENCHMARK_INT_COLUMNS = {
    "k",
    "min_cluster_size",
    "min_samples",
    "random_seed",
    "num_clusters",
    "noise_points",
}
BENCHMARK_BOOL_COLUMNS = {"tiny_cluster_flag"}


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def parse_bool(value: str | None) -> bool | None:
    if value in (None, ""):
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    return None


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        return None
    return parsed


def parse_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def load_benchmark_rows(analysis_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method_name in METHOD_NAMES:
        benchmark_path = analysis_root / method_name / "benchmark_results.csv"
        if not benchmark_path.exists():
            continue
        for raw_row in load_csv_rows(benchmark_path):
            row: dict[str, Any] = dict(raw_row)
            for column in BENCHMARK_FLOAT_COLUMNS:
                row[column] = parse_float(raw_row.get(column))
            for column in BENCHMARK_INT_COLUMNS:
                row[column] = parse_int(raw_row.get(column))
            for column in BENCHMARK_BOOL_COLUMNS:
                row[column] = parse_bool(raw_row.get(column))
            row["cluster_size_distribution_values"] = parse_cluster_size_distribution(
                raw_row.get("cluster_size_distribution", "")
            )
            row["benchmark_results_csv"] = str(benchmark_path)
            row["assignments_csv"] = str(resolve_assignment_path(analysis_root, raw_row["candidate_id"]))
            rows.append(row)
    return rows


def resolve_assignment_path(analysis_root: Path, candidate_id: str) -> Path:
    parts = candidate_id.split("__")
    if len(parts) < 2:
        raise RuntimeError(f"Could not infer method name from candidate id: {candidate_id}")
    method_name = parts[1]
    path = analysis_root / method_name / "assignments" / f"{candidate_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Assignment file not found for candidate {candidate_id}: {path}")
    return path


def find_candidate_result(analysis_root: Path, candidate_id: str) -> dict[str, Any]:
    for row in load_benchmark_rows(analysis_root):
        if row["candidate_id"] == candidate_id:
            return row
    raise RuntimeError(f"Candidate id not found in benchmark results: {candidate_id}")


def parse_cluster_size_distribution(raw_value: str) -> list[dict[str, int]]:
    if not raw_value:
        return []
    parsed = json.loads(raw_value)
    return [{"label": int(item["label"]), "count": int(item["count"])} for item in parsed]


def build_lookup(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if value in (None, ""):
            continue
        if value in lookup:
            raise RuntimeError(f"Duplicate key value {value!r} for key {key}")
        lookup[value] = row
    return lookup


def load_dataset_rows(path: Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    rows = load_csv_rows(path)
    if not rows:
        raise RuntimeError(f"Dataset CSV is empty: {path}")
    headers = list(rows[0].keys())
    feature_columns = [column for column in headers if column not in NON_FEATURE_COLUMNS]
    return rows, headers, feature_columns


def get_feature_matrix(
    rows: list[dict[str, str]],
    feature_columns: list[str],
) -> tuple[list[str], np.ndarray]:
    image_ids: list[str] = []
    matrix = np.empty((len(rows), len(feature_columns)), dtype=np.float64)
    for row_index, row in enumerate(rows):
        image_id = row.get("image_id")
        if not image_id:
            raise RuntimeError(f"Dataset row {row_index} is missing image_id")
        image_ids.append(image_id)
        for column_index, column in enumerate(feature_columns):
            raw_value = row.get(column)
            parsed = parse_float(raw_value)
            if parsed is None:
                raise RuntimeError(f"Missing numeric feature value for image {image_id}: {column}")
            matrix[row_index, column_index] = parsed
    return image_ids, matrix


def load_candidate_labels(assignments_csv: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    rows = load_csv_rows(assignments_csv)
    if not rows:
        raise RuntimeError(f"Assignments CSV is empty: {assignments_csv}")
    labels_by_image_id: dict[str, int] = {}
    for row in rows:
        image_id = row.get("image_id")
        if not image_id:
            raise RuntimeError(f"Assignment row is missing image_id: {assignments_csv}")
        labels_by_image_id[image_id] = int(row["cluster_label"])
    return rows, labels_by_image_id


def align_rows_and_labels(
    dataset_rows: list[dict[str, str]],
    feature_columns: list[str],
    labels_by_image_id: dict[str, int],
) -> tuple[list[dict[str, str]], np.ndarray, np.ndarray]:
    aligned_rows: list[dict[str, str]] = []
    labels: list[int] = []
    matrix_rows: list[np.ndarray] = []

    for row in dataset_rows:
        image_id = row.get("image_id")
        if image_id not in labels_by_image_id:
            continue
        aligned_rows.append(row)
        labels.append(labels_by_image_id[image_id])
        matrix_rows.append(np.array([float(row[column]) for column in feature_columns], dtype=np.float64))

    if not aligned_rows:
        raise RuntimeError("No overlapping image_ids were found between the dataset and assignments")

    return aligned_rows, np.vstack(matrix_rows), np.asarray(labels, dtype=int)


def align_projection_to_labels(
    projection_csv: Path,
    labels_by_image_id: dict[str, int],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    projection_rows = load_csv_rows(projection_csv)
    points = []
    labels = []
    image_ids = []
    for row in projection_rows:
        image_id = row.get("image_id")
        if image_id not in labels_by_image_id:
            continue
        pc1 = parse_float(row.get("PC1"))
        pc2 = parse_float(row.get("PC2"))
        if pc1 is None or pc2 is None:
            continue
        image_ids.append(image_id)
        labels.append(labels_by_image_id[image_id])
        points.append((pc1, pc2))
    if not points:
        raise RuntimeError(f"No overlapping PCA projection rows found in {projection_csv}")
    return np.asarray(points, dtype=np.float64), np.asarray(labels, dtype=int), image_ids


def cluster_distribution_entropy(distribution: list[dict[str, int]]) -> float | None:
    non_noise_counts = [item["count"] for item in distribution if int(item["label"]) != -1]
    if len(non_noise_counts) < 2:
        return None
    total = float(sum(non_noise_counts))
    probabilities = np.asarray(non_noise_counts, dtype=np.float64) / total
    entropy = -float(np.sum(probabilities * np.log(probabilities + 1e-12)))
    return float(entropy / math.log(len(non_noise_counts)))


def safe_rank_normalize(values: list[float], higher_is_better: bool) -> list[float]:
    if not values:
        return []
    minimum = min(values)
    maximum = max(values)
    if math.isclose(minimum, maximum):
        return [1.0 for _ in values]
    if higher_is_better:
        return [(value - minimum) / (maximum - minimum) for value in values]
    return [(maximum - value) / (maximum - minimum) for value in values]


def benjamini_hochberg(p_values: list[float | None]) -> list[float | None]:
    indexed = [(index, value) for index, value in enumerate(p_values) if value is not None]
    if not indexed:
        return [None for _ in p_values]

    indexed.sort(key=lambda item: item[1])
    total = len(indexed)
    adjusted_pairs: list[tuple[int, float]] = []
    running_min = 1.0
    for reverse_rank, (original_index, value) in enumerate(reversed(indexed), start=1):
        rank = total - reverse_rank + 1
        adjusted = min(1.0, value * total / rank)
        running_min = min(running_min, adjusted)
        adjusted_pairs.append((original_index, running_min))

    adjusted_pairs.reverse()
    adjusted_lookup = {index: value for index, value in adjusted_pairs}
    return [adjusted_lookup.get(index) for index in range(len(p_values))]


def maybe_import_scipy_stats() -> Any | None:
    try:
        from scipy import stats
    except ImportError:
        return None
    return stats


def maybe_import_sklearn_inspection() -> dict[str, Any] | None:
    try:
        from sklearn.feature_extraction import DictVectorizer
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None

    return {
        "DictVectorizer": DictVectorizer,
        "RandomForestClassifier": RandomForestClassifier,
        "LogisticRegression": LogisticRegression,
        "StratifiedKFold": StratifiedKFold,
        "StandardScaler": StandardScaler,
        "cross_val_score": cross_val_score,
    }


def capture_date_parts(raw_value: str | None) -> dict[str, str | int | None]:
    if not raw_value:
        return {"capture_year": None, "capture_month": None, "capture_season": None}
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        try:
            parsed = datetime.strptime(raw_value, "%Y-%m-%d")
        except ValueError:
            return {"capture_year": None, "capture_month": None, "capture_season": None}

    month = parsed.month
    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "autumn"
    return {"capture_year": parsed.year, "capture_month": month, "capture_season": season}


def top_n_labels(labels: np.ndarray) -> list[int]:
    ordered = sorted({int(label) for label in labels.tolist() if int(label) != -1})
    return ordered


def plot_scatter_by_cluster(
    output_path: Path,
    points: np.ndarray,
    labels: np.ndarray,
    title: str,
    xlabel: str,
    ylabel: str,
) -> str | None:
    plt = import_pyplot()
    if plt is None:
        return None

    figure, axis = plt.subplots(figsize=(7, 6))
    unique_labels = sorted({int(label) for label in labels.tolist()})
    color_map = plt.cm.get_cmap("tab10", max(len(unique_labels), 3))
    for color_index, cluster_label in enumerate(unique_labels):
        mask = labels == cluster_label
        label_name = "noise" if cluster_label == -1 else f"cluster {cluster_label}"
        axis.scatter(
            points[mask, 0],
            points[mask, 1],
            s=14,
            alpha=0.72,
            label=label_name,
            color=color_map(color_index),
        )
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def plot_heatmap(
    output_path: Path,
    matrix: np.ndarray,
    row_labels: list[str],
    column_labels: list[str],
    title: str,
    cmap: str = "coolwarm",
) -> str | None:
    plt = import_pyplot()
    if plt is None:
        return None

    height = max(3.0, 0.35 * len(row_labels))
    width = max(8.0, 0.30 * len(column_labels))
    figure, axis = plt.subplots(figsize=(width, height))
    image = axis.imshow(matrix, aspect="auto", cmap=cmap)
    axis.set_xticks(np.arange(len(column_labels)))
    axis.set_xticklabels(column_labels, rotation=60, ha="right")
    axis.set_yticks(np.arange(len(row_labels)))
    axis.set_yticklabels(row_labels)
    axis.set_title(title)
    figure.colorbar(image, ax=axis, fraction=0.025, pad=0.02)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def summarize_cluster_counts(labels: np.ndarray) -> list[dict[str, Any]]:
    counts = Counter(int(label) for label in labels.tolist())
    total = int(labels.shape[0])
    rows = []
    for cluster_label in sorted(counts):
        rows.append(
            {
                "cluster_label": cluster_label,
                "count": counts[cluster_label],
                "fraction": counts[cluster_label] / total if total else 0.0,
            }
        )
    return rows


def join_image_paths(
    representative_rows: list[dict[str, Any]],
    image_paths_csv: Path | None,
) -> list[dict[str, Any]]:
    if image_paths_csv is None:
        return representative_rows

    lookup = build_lookup(load_csv_rows(image_paths_csv), "image_id")
    joined_rows: list[dict[str, Any]] = []
    for row in representative_rows:
        joined = dict(row)
        image_path = lookup.get(row["image_id"], {}).get("image_path", "")
        joined["image_path"] = image_path
        joined_rows.append(joined)
    return joined_rows


def maybe_export_contact_sheets(
    representative_rows: list[dict[str, Any]],
    output_dir: Path,
    title_prefix: str,
) -> list[str]:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return []

    def load_image_reference(image_reference: str) -> Any | None:
        if not image_reference:
            return None

        local_path = Path(image_reference)
        if local_path.exists():
            try:
                return Image.open(local_path).convert("RGB")
            except OSError:
                return None

        parsed = urlparse(image_reference)
        if parsed.scheme not in {"http", "https"}:
            return None

        dotenv_loaded = False
        if "MINIO_ENDPOINT" not in os.environ:
            try:
                from dotenv import load_dotenv

                load_dotenv(".env")
                dotenv_loaded = True
            except ImportError:
                dotenv_loaded = False

        minio_endpoint = os.getenv("MINIO_ENDPOINT")
        minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        secure = parsed.scheme == "https"

        if minio_endpoint and minio_access_key and minio_secret_key:
            try:
                from minio import Minio
            except ImportError:
                pass
            else:
                bucket_and_object = parsed.path.lstrip("/").split("/", 1)
                if len(bucket_and_object) == 2:
                    bucket_name, object_name = bucket_and_object
                    endpoint = parsed.netloc or minio_endpoint
                    client = Minio(
                        endpoint,
                        access_key=minio_access_key,
                        secret_key=minio_secret_key,
                        secure=secure,
                    )
                    try:
                        response = client.get_object(bucket_name, object_name)
                        data = response.read()
                        response.close()
                        response.release_conn()
                        return Image.open(BytesIO(data)).convert("RGB")
                    except Exception:
                        pass

        try:
            from urllib.request import urlopen

            with urlopen(image_reference, timeout=10) as response:
                data = response.read()
            return Image.open(BytesIO(data)).convert("RGB")
        except Exception:
            return None

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in representative_rows:
        if row.get("image_path"):
            grouped[int(row["cluster_label"])].append(row)

    exported_paths: list[str] = []
    for cluster_label, rows in grouped.items():
        opened_images = []
        labels = []
        for row in rows:
            image = load_image_reference(str(row["image_path"]))
            if image is None:
                continue
            opened_images.append(image)
            rank_value = row.get("rank_in_cluster", row.get("rank_within_cluster", ""))
            labels.append(f"{row['image_id']}\nrank {rank_value}")

        if not opened_images:
            continue

        thumb_size = (180, 180)
        caption_height = 40
        columns = min(3, len(opened_images))
        rows_count = int(math.ceil(len(opened_images) / columns))
        canvas = Image.new("RGB", (columns * thumb_size[0], rows_count * (thumb_size[1] + caption_height)), "white")
        draw = ImageDraw.Draw(canvas)

        for index, image in enumerate(opened_images):
            thumbnail = image.copy()
            thumbnail.thumbnail(thumb_size)
            column_index = index % columns
            row_index = index // columns
            x_offset = column_index * thumb_size[0]
            y_offset = row_index * (thumb_size[1] + caption_height)
            paste_x = x_offset + (thumb_size[0] - thumbnail.width) // 2
            paste_y = y_offset + (thumb_size[1] - thumbnail.height) // 2
            canvas.paste(thumbnail, (paste_x, paste_y))
            draw.text((x_offset + 4, y_offset + thumb_size[1] + 4), labels[index], fill="black")

        contact_sheet_path = output_dir / f"{title_prefix}_cluster_{cluster_label}.png"
        canvas.save(contact_sheet_path)
        exported_paths.append(str(contact_sheet_path))

    return exported_paths


def write_rows_and_summary(
    output_dir: Path,
    summary_name: str,
    summary_payload: dict[str, Any],
    extra_csvs: list[tuple[str, list[dict[str, Any]], list[str]]],
) -> None:
    for filename, rows, fieldnames in extra_csvs:
        write_csv(output_dir / filename, rows, fieldnames)
    write_json(output_dir / summary_name, summary_payload)
