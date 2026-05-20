#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from iteration2.build_dataset import (  # type: ignore
    ID_COLUMNS,
    preprocess_feature_rows,
    reduce_feature_rows,
    write_csv,
)


def load_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def build_manual_labels(path: Path) -> dict[str, str]:
    rows, _ = load_csv_rows(path)
    labels: dict[str, str] = {}
    for row in rows:
        image_id = (row.get("image_id") or "").strip()
        manual_label = (row.get("manual_grid_label") or "").strip()
        if image_id and manual_label:
            labels[image_id] = manual_label
    return labels


def build_predicted_labels(path: Path) -> dict[str, str]:
    rows, _ = load_csv_rows(path)
    labels: dict[str, str] = {}
    for row in rows:
        image_id = (row.get("image_id") or "").strip()
        predicted_label = (row.get("roi_grid_label") or "").strip()
        if image_id and predicted_label:
            labels[image_id] = predicted_label
    return labels


def resolve_final_label(image_id: str, manual_labels: dict[str, str], predicted_labels: dict[str, str]) -> tuple[str, str]:
    manual_label = manual_labels.get(image_id, "").strip()
    if manual_label:
        return manual_label, "manual_label"
    predicted_label = predicted_labels.get(image_id, "").strip()
    if predicted_label == "grid":
        return "grid", "predicted_grid"
    if predicted_label in {"no_grid", "uncertain"}:
        return "no_grid", "predicted_non_grid_rule"
    return "unknown", "missing_prediction"


def enrich_grid_labels(
    rows: list[dict[str, str]],
    manual_labels: dict[str, str],
    predicted_labels: dict[str, str],
) -> tuple[list[dict[str, str]], Counter[str], Counter[str]]:
    final_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        image_id = (row.get("image_id") or "").strip()
        final_label, label_source = resolve_final_label(image_id, manual_labels, predicted_labels)
        enriched = dict(row)
        enriched["manual_grid_label"] = manual_labels.get(image_id, "").strip()
        enriched["roi_grid_label"] = predicted_labels.get(image_id, "").strip()
        enriched["final_grid_label"] = final_label
        enriched["final_grid_label_source"] = label_source
        enriched_rows.append(enriched)
        final_counter[final_label] += 1
        source_counter[label_source] += 1
    return enriched_rows, final_counter, source_counter


def filter_by_ids(rows: list[dict[str, str]], kept_ids: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if (row.get("image_id") or "").strip() in kept_ids]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reuse the iteration2 enriched dataset, but keep only images classified as no-grid in iteration3b."
    )
    parser.add_argument(
        "--iteration2-dataset-dir",
        default="iteration2/output/dataset",
        help="Directory containing the existing iteration2 dataset outputs.",
    )
    parser.add_argument(
        "--grid-review-csv",
        default="iteration3b/output/grid_review/grid_review_simple.csv",
        help="Manual review CSV produced in iteration3b.",
    )
    parser.add_argument(
        "--grid-predictions-csv",
        default="iteration3b/output/dataset/image_features_enriched.csv",
        help="Iteration3 dataset CSV containing roi_grid_label predictions.",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration3b/output/no_grid_from_iteration2",
        help="Directory where the iteration2-style no-grid subset will be written.",
    )
    args = parser.parse_args()

    iteration2_dir = Path(args.iteration2_dataset_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    review_csv = Path(args.grid_review_csv).resolve()
    predictions_csv = Path(args.grid_predictions_csv).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manual_labels = build_manual_labels(review_csv)
    predicted_labels = build_predicted_labels(predictions_csv)

    image_features_rows, image_features_fields = load_csv_rows(iteration2_dir / "image_features_enriched.csv")
    images_metadata_rows, images_metadata_fields = load_csv_rows(iteration2_dir / "images_metadata.csv")
    particles_rows, particles_fields = load_csv_rows(iteration2_dir / "particles.csv")
    places_rows, places_fields = load_csv_rows(iteration2_dir / "places_features.csv") if (iteration2_dir / "places_features.csv").exists() else ([], [])

    enriched_features, final_counter, source_counter = enrich_grid_labels(
        image_features_rows,
        manual_labels,
        predicted_labels,
    )
    enriched_metadata, _, _ = enrich_grid_labels(
        images_metadata_rows,
        manual_labels,
        predicted_labels,
    )

    kept_feature_rows = [row for row in enriched_features if row.get("final_grid_label") == "no_grid"]
    kept_ids = {(row.get("image_id") or "").strip() for row in kept_feature_rows}
    kept_metadata_rows = filter_by_ids(enriched_metadata, kept_ids)
    kept_particle_rows = filter_by_ids(particles_rows, kept_ids)
    kept_places_rows = [
        row
        for row in places_rows
        if ((row.get("sensor_id") or row.get("image_id") or "").strip() in kept_ids)
    ]

    feature_sets = {
        "core": [],
        "extended": [],
        "phase6_default": [],
    }
    preprocessed_rows, eligible_rows, preprocessing_report, scaled_matrix, kept_columns = preprocess_feature_rows(
        kept_feature_rows,
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

    image_features_output_fields = image_features_fields + [
        field for field in ("manual_grid_label", "roi_grid_label", "final_grid_label", "final_grid_label_source")
        if field not in image_features_fields
    ]
    images_metadata_output_fields = images_metadata_fields + [
        field for field in ("manual_grid_label", "roi_grid_label", "final_grid_label", "final_grid_label_source")
        if field not in images_metadata_fields
    ]

    write_csv(output_dir / "image_features_enriched.csv", kept_feature_rows, image_features_output_fields)
    write_csv(output_dir / "images_metadata.csv", kept_metadata_rows, images_metadata_output_fields)
    write_csv(output_dir / "particles.csv", kept_particle_rows, particles_fields)
    if kept_places_rows:
        write_csv(output_dir / "places_features.csv", kept_places_rows, places_fields)

    report = {
        "iteration2_dataset_dir": str(iteration2_dir),
        "grid_review_csv": str(review_csv),
        "grid_predictions_csv": str(predictions_csv),
        "output_dir": str(output_dir),
        "manual_labels_count": len(manual_labels),
        "predicted_labels_count": len(predicted_labels),
        "final_grid_label_counts": dict(final_counter),
        "final_grid_label_source_counts": dict(source_counter),
        "kept_image_count": len(kept_feature_rows),
        "kept_particle_count": len(kept_particle_rows),
        "kept_places_rows": len(kept_places_rows),
        "eligible_rows_for_phase5_and_phase6": len(eligible_rows),
        "final_rows": len(reduced_rows),
        "rule_used_for_unlabeled_rows": {
            "grid": "exclude when roi_grid_label == grid",
            "no_grid": "keep when roi_grid_label == no_grid",
            "uncertain": "keep as no_grid based on current manual sample",
            "blank_or_missing": "exclude",
        },
        "phase5": preprocessing_report,
        "phase6": reduction_report,
        "raw_output_files": {
            "images_metadata_csv": str(output_dir / "images_metadata.csv"),
            "particles_csv": str(output_dir / "particles.csv"),
            "places_features_csv": str(output_dir / "places_features.csv") if kept_places_rows else None,
            "image_features_enriched_csv": str(output_dir / "image_features_enriched.csv"),
            "image_features_preprocessed_csv": str(output_dir / "image_features_preprocessed.csv"),
            "image_features_final_csv": str(output_dir / "image_features_final.csv"),
        },
        "raw_output_columns": {
            "image_features_preprocessed_csv": preprocessed_columns,
            "image_features_final_csv": final_columns,
        },
    }
    (output_dir / "filter_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
