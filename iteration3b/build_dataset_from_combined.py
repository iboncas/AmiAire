#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SRC = REPO_ROOT / "analysis-service" / "src"
DATA_DIR = REPO_ROOT / "data"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(ANALYSIS_SRC) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_SRC))
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

from combine import iter_json_array  # type: ignore
from dataset_features import build_empty_image_feature_record, build_image_metadata_record, get_feature_set_catalog  # type: ignore
from pipeline import process_roi  # type: ignore
from roi_extraction import extract_roi_from_image_array  # type: ignore
from iteration2.build_dataset import COLOR_FEATURE_COLUMNS, compute_color_features_from_encoded_roi  # type: ignore


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


def normalize_mongo_value(value: Any) -> Any:
    if isinstance(value, dict):
        if "$oid" in value:
            return str(value["$oid"])
        if "$numberDouble" in value:
            return float(value["$numberDouble"])
        if "$numberInt" in value:
            return int(value["$numberInt"])
        if "$numberLong" in value:
            return int(value["$numberLong"])
        if "$numberDecimal" in value:
            return float(value["$numberDecimal"])
        return {key: normalize_mongo_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [normalize_mongo_value(inner) for inner in value]
    return value


def first_present(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def to_float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def decode_base64_image(image_b64: str | None) -> np.ndarray | None:
    if not image_b64 or not isinstance(image_b64, str):
        return None
    payload = image_b64.split(",", 1)[1] if image_b64.startswith("data:") and "," in image_b64 else image_b64
    try:
        image_bytes = base64.b64decode(payload)
    except Exception:
        return None
    image_array = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(image_array, cv2.IMREAD_COLOR)


def csv_ready_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], preferred_columns: list[str] | None = None) -> list[str]:
    preferred_columns = preferred_columns or []
    columns: list[str] = []
    seen = set()
    for column in preferred_columns:
        if column not in seen:
            columns.append(column)
            seen.add(column)
    for row in rows:
        for column in row.keys():
            if column not in seen:
                columns.append(column)
                seen.add(column)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_ready_value(row.get(column)) for column in columns})
    return columns


def build_metadata(record: dict[str, Any], image_id: str) -> dict[str, Any]:
    return {
        "image_id": image_id,
        "sensor_id": image_id,
        "capture_datetime": first_present(record, "Fecha de inicio", "fechaInicio") or "",
        "collection_datetime": first_present(record, "Fecha de recogida", "fechaRecogida") or "",
        "latitude": to_float_or_none(first_present(record, "Localización latitud", "ubicacion.latitud")),
        "longitude": to_float_or_none(first_present(record, "Localización longitud", "ubicacion.longitud")),
        "image_path": f"combined.json:{image_id}",
        "official_station_id": "",
    }


def build_context(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_pm10": to_float_or_none(first_present(record, "PM10", "metricas.pm10")),
        "record_pm25": to_float_or_none(first_present(record, "PM2.5", "metricas.pm25")),
        "record_pollution_level": first_present(record, "Nivel de polución", "Nivel de polucion", "nivelPolucion") or "",
        "official_station_name": "",
        "official_station_distance_km": None,
        "official_pm10": None,
        "official_pm25": None,
        "official_fetched_at": "",
    }


def build_empty_result(metadata: dict[str, Any], context: dict[str, Any], failure_reason: str) -> dict[str, Any]:
    metadata_row = build_image_metadata_record(
        metadata=metadata,
        roi_shape=None,
        roi_detected=False,
        analysis_success=False,
        segmentation_success=False,
        failure_reason=failure_reason,
    )
    feature_row = build_empty_image_feature_record(metadata_row, contextual_data=context)
    for column in COLOR_FEATURE_COLUMNS:
        feature_row[column] = None
    return {
        "images_metadata": metadata_row,
        "particles": [],
        "image_features": feature_row,
        "feature_sets": get_feature_set_catalog(),
    }


def process_record(record: dict[str, Any], model_type: str) -> tuple[dict[str, Any], str]:
    normalized = normalize_mongo_value(record)
    image_id = str(first_present(normalized, "_id", "id") or "")
    metadata = build_metadata(normalized, image_id)
    context = build_context(normalized)
    image_b64 = first_present(normalized, "Imagen de entrada", "imagen", "image", "base64", "imageB64", "image_b64")
    image_bgr = decode_base64_image(image_b64)
    if image_bgr is None:
        return build_empty_result(metadata, context, "image_not_available"), "image_not_available"

    _contour_image, roi = extract_roi_from_image_array(image_bgr)
    if roi is None:
        return build_empty_result(metadata, context, "roi_not_detected"), "roi_not_detected"

    pipeline_results = process_roi(
        roi,
        model_type=model_type,
        image_metadata=metadata,
        contextual_data=context,
    )
    roi_ok, roi_encoded = cv2.imencode(".png", roi)
    roi_b64 = base64.b64encode(roi_encoded).decode("utf-8") if roi_ok else None
    image_features = pipeline_results["dataset_outputs"].get("image_features") or {}
    image_features.update(
        compute_color_features_from_encoded_roi(
            roi_b64,
            pipeline_results.get("binary_mask_b64"),
        )
    )
    pipeline_results["dataset_outputs"]["image_features"] = image_features
    return pipeline_results["dataset_outputs"], "success"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build iteration3b dataset directly from data/combined.json.")
    parser.add_argument(
        "--input-json",
        default="data/combined.json",
        help="Path to the combined JSON array file.",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration3b/output/dataset",
        help="Directory where CSV and JSON outputs will be written.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of records to process.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Optional number of records to skip before processing.",
    )
    parser.add_argument(
        "--model-type",
        default="PM10",
        choices=["PM10", "PM25"],
        help="Passed through to the existing pollution output code. Grid detection itself is model-agnostic.",
    )
    args = parser.parse_args()

    input_json = Path(args.input_json).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    images_metadata_rows: list[dict[str, Any]] = []
    particle_rows: list[dict[str, Any]] = []
    image_feature_rows: list[dict[str, Any]] = []
    feature_sets = get_feature_set_catalog()
    summary = {
        "input_json": str(input_json),
        "output_dir": str(output_dir),
        "processed_records": 0,
        "successful_analyses": 0,
        "roi_failures": 0,
        "missing_images": 0,
        "other_failures": 0,
    }

    for index, record in enumerate(iter_json_array(input_json)):
        if index < args.offset:
            continue
        if args.limit > 0 and summary["processed_records"] >= args.limit:
            break

        dataset_outputs, status_label = process_record(record, args.model_type)
        images_metadata = dataset_outputs.get("images_metadata") or {}
        particles = dataset_outputs.get("particles") or []
        image_features = dataset_outputs.get("image_features") or {}
        returned_feature_sets = dataset_outputs.get("feature_sets") or {}

        images_metadata_rows.append(images_metadata)
        particle_rows.extend(particles)
        image_feature_rows.append(image_features)

        if returned_feature_sets.get("extended"):
            feature_sets = returned_feature_sets

        summary["processed_records"] += 1
        if status_label == "success":
            summary["successful_analyses"] += 1
        elif status_label == "image_not_available":
            summary["missing_images"] += 1
        elif status_label == "roi_not_detected":
            summary["roi_failures"] += 1
        else:
            summary["other_failures"] += 1

        if summary["processed_records"] % 25 == 0:
            print(f"Processed {summary['processed_records']} records", flush=True)

    image_columns = write_csv(output_dir / "images_metadata.csv", images_metadata_rows, preferred_columns=METADATA_COLUMNS)
    particle_columns = write_csv(output_dir / "particles.csv", particle_rows, preferred_columns=["image_id", "particle_id"])
    feature_columns = write_csv(
        output_dir / "image_features_enriched.csv",
        image_feature_rows,
        preferred_columns=METADATA_COLUMNS + CONTEXT_COLUMNS,
    )

    report = {
        "summary": summary,
        "feature_sets": feature_sets,
        "raw_output_files": {
            "images_metadata_csv": str(output_dir / "images_metadata.csv"),
            "particles_csv": str(output_dir / "particles.csv"),
            "image_features_enriched_csv": str(output_dir / "image_features_enriched.csv"),
        },
        "raw_output_columns": {
            "images_metadata_csv": image_columns,
            "particles_csv": particle_columns,
            "image_features_enriched_csv": feature_columns,
        },
    }
    with (output_dir / "build_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
