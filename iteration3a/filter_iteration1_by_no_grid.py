#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def resolve_final_label(
    image_id: str,
    manual_labels: dict[str, str],
    predicted_labels: dict[str, str],
) -> tuple[str, str]:
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


def project_rows(rows: list[dict[str, str]], fieldnames: list[str]) -> list[dict[str, str]]:
    return [{field: row.get(field, "") for field in fieldnames} for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reuse the iteration1 final dataset, but keep only images classified as no-grid in iteration3a."
    )
    parser.add_argument(
        "--iteration1-dataset-dir",
        default="iteration1/output/dataset",
        help="Directory containing iteration1 image_features_final.csv and image_manifest.csv.",
    )
    parser.add_argument(
        "--grid-review-csv",
        default="iteration3a/output/grid_review/grid_review_simple.csv",
        help="Manual review CSV produced in iteration3a.",
    )
    parser.add_argument(
        "--grid-predictions-csv",
        default="iteration3a/output/dataset/image_features_enriched.csv",
        help="Iteration3a dataset CSV containing roi_grid_label predictions.",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration3a/output/no_grid_from_iteration1",
        help="Directory where the iteration1-style no-grid subset will be written.",
    )
    args = parser.parse_args()

    iteration1_dir = Path(args.iteration1_dataset_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    review_csv = Path(args.grid_review_csv).resolve()
    predictions_csv = Path(args.grid_predictions_csv).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manual_labels = build_manual_labels(review_csv)
    predicted_labels = build_predicted_labels(predictions_csv)

    feature_rows, feature_fields = load_csv_rows(iteration1_dir / "image_features_final.csv")
    manifest_rows, manifest_fields = load_csv_rows(iteration1_dir / "image_manifest.csv")

    enriched_features, final_counter, source_counter = enrich_grid_labels(
        feature_rows,
        manual_labels,
        predicted_labels,
    )
    enriched_manifest, _, _ = enrich_grid_labels(
        manifest_rows,
        manual_labels,
        predicted_labels,
    )

    kept_feature_rows = [row for row in enriched_features if row.get("final_grid_label") == "no_grid"]
    kept_ids = {(row.get("image_id") or "").strip() for row in kept_feature_rows}
    kept_manifest_rows = filter_by_ids(enriched_manifest, kept_ids)

    # Preserve the original iteration1 clustering matrix unchanged.
    write_csv(
        output_dir / "image_features_final.csv",
        project_rows(kept_feature_rows, feature_fields),
        feature_fields,
    )
    write_csv(
        output_dir / "image_manifest.csv",
        project_rows(kept_manifest_rows, manifest_fields),
        manifest_fields,
    )

    grid_decision_fields = [
        "image_id",
        "roi_grid_label",
        "manual_grid_label",
        "final_grid_label",
        "final_grid_label_source",
    ]
    grid_decision_rows = [
        {field: row.get(field, "") for field in grid_decision_fields}
        for row in enriched_features
    ]
    write_csv(output_dir / "grid_decisions.csv", grid_decision_rows, grid_decision_fields)

    report = {
        "iteration1_dataset_dir": str(iteration1_dir),
        "grid_review_csv": str(review_csv),
        "grid_predictions_csv": str(predictions_csv),
        "output_dir": str(output_dir),
        "manual_labels_count": len(manual_labels),
        "predicted_labels_count": len(predicted_labels),
        "final_grid_label_counts": dict(final_counter),
        "final_grid_label_source_counts": dict(source_counter),
        "kept_image_count": len(kept_feature_rows),
        "kept_manifest_rows": len(kept_manifest_rows),
        "rule_used_for_unlabeled_rows": {
            "grid": "exclude when roi_grid_label == grid",
            "no_grid": "keep when roi_grid_label == no_grid",
            "uncertain": "keep as no_grid based on current manual sample",
            "blank_or_missing": "exclude",
        },
        "raw_output_files": {
            "image_features_final_csv": str(output_dir / "image_features_final.csv"),
            "image_manifest_csv": str(output_dir / "image_manifest.csv"),
            "grid_decisions_csv": str(output_dir / "grid_decisions.csv"),
        },
    }
    with (output_dir / "filter_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
