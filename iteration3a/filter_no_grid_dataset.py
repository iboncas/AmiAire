#!/usr/bin/env python3
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
        label = (row.get("manual_grid_label") or "").strip()
        if image_id and label:
            labels[image_id] = label
    return labels


def resolve_final_label(
    image_id: str,
    predicted_label: str,
    manual_labels: dict[str, str],
) -> tuple[str, str]:
    manual_label = manual_labels.get(image_id, "").strip()
    if manual_label:
        return manual_label, "manual_label"
    if predicted_label == "grid":
        return "grid", "predicted_grid"
    if predicted_label in {"no_grid", "uncertain"}:
        return "no_grid", "predicted_non_grid_rule"
    return "unknown", "missing_prediction"


def enrich_rows(
    rows: list[dict[str, str]],
    manual_labels: dict[str, str],
) -> tuple[list[dict[str, str]], Counter[str], Counter[str]]:
    final_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    enriched: list[dict[str, str]] = []
    for row in rows:
        enriched_row = dict(row)
        image_id = (row.get("image_id") or "").strip()
        predicted_label = (row.get("roi_grid_label") or "").strip()
        final_label, label_source = resolve_final_label(image_id, predicted_label, manual_labels)
        enriched_row["manual_grid_label"] = manual_labels.get(image_id, "").strip()
        enriched_row["final_grid_label"] = final_label
        enriched_row["final_grid_label_source"] = label_source
        enriched.append(enriched_row)
        final_counter[final_label] += 1
        source_counter[label_source] += 1
    return enriched, final_counter, source_counter


def filter_particles(rows: list[dict[str, str]], kept_ids: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if (row.get("image_id") or "").strip() in kept_ids]


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter iteration3a dataset down to no-grid images only.")
    parser.add_argument(
        "--dataset-dir",
        default="iteration3a/output/dataset",
        help="Directory containing images_metadata.csv, image_features_enriched.csv, and particles.csv.",
    )
    parser.add_argument(
        "--review-csv",
        default="iteration3a/output/grid_review/grid_review_simple.csv",
        help="Minimal manual review CSV with manual_grid_label filled where available.",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration3a/output/no_grid_dataset",
        help="Directory where the filtered no-grid-only dataset will be written.",
    )
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    review_csv = Path(args.review_csv).resolve()

    manual_labels = build_manual_labels(review_csv)

    image_features_rows, image_features_fields = load_csv_rows(dataset_dir / "image_features_enriched.csv")
    images_metadata_rows, images_metadata_fields = load_csv_rows(dataset_dir / "images_metadata.csv")
    particles_rows, particles_fields = load_csv_rows(dataset_dir / "particles.csv")

    enriched_features, final_counter, source_counter = enrich_rows(image_features_rows, manual_labels)
    enriched_metadata, _, _ = enrich_rows(images_metadata_rows, manual_labels)

    kept_feature_rows = [row for row in enriched_features if row.get("final_grid_label") == "no_grid"]
    kept_ids = {(row.get("image_id") or "").strip() for row in kept_feature_rows}
    kept_metadata_rows = [row for row in enriched_metadata if (row.get("image_id") or "").strip() in kept_ids]
    kept_particle_rows = filter_particles(particles_rows, kept_ids)

    image_features_output_fields = image_features_fields + [
        field for field in ("manual_grid_label", "final_grid_label", "final_grid_label_source")
        if field not in image_features_fields
    ]
    images_metadata_output_fields = images_metadata_fields + [
        field for field in ("manual_grid_label", "final_grid_label", "final_grid_label_source")
        if field not in images_metadata_fields
    ]

    write_csv(output_dir / "image_features_enriched.csv", kept_feature_rows, image_features_output_fields)
    write_csv(output_dir / "images_metadata.csv", kept_metadata_rows, images_metadata_output_fields)
    write_csv(output_dir / "particles.csv", kept_particle_rows, particles_fields)

    report = {
        "dataset_dir": str(dataset_dir),
        "review_csv": str(review_csv),
        "output_dir": str(output_dir),
        "manual_labels_count": len(manual_labels),
        "final_grid_label_counts": dict(final_counter),
        "final_grid_label_source_counts": dict(source_counter),
        "kept_image_count": len(kept_feature_rows),
        "kept_particle_count": len(kept_particle_rows),
        "rule_used_for_unlabeled_rows": {
            "grid": "exclude when roi_grid_label == grid",
            "no_grid": "keep when roi_grid_label == no_grid",
            "uncertain": "keep as no_grid based on current manual sample",
            "blank_or_missing": "exclude",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "filter_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
