#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from iteration2.build_dataset import (  # type: ignore
    CONTEXT_COLUMNS,
    EXTENDED_FEATURE_SET_FALLBACK,
    ID_COLUMNS,
    METADATA_COLUMNS,
    PHASE6_DEFAULT_FALLBACK,
    PLACES_ALL_COLUMNS,
    TEMPORAL_ENRICHED_COLUMNS,
    derive_temporal_features,
    load_places_features,
    merge_feature_lists,
    merge_places_into_feature_row,
    preprocess_feature_rows,
    reduce_feature_rows,
    write_csv,
)


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def enrich_image_feature_row(row: dict[str, Any], places_row: dict[str, Any] | None) -> dict[str, Any]:
    enriched = dict(row)
    enriched = merge_places_into_feature_row(enriched, places_row)
    enriched.update(derive_temporal_features(row.get("capture_datetime")))
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the iteration-2 style temporal and Places enrichment to the no-grid iteration3b dataset."
    )
    parser.add_argument(
        "--input-csv",
        default="iteration3b/output/no_grid_dataset/image_features_enriched.csv",
        help="Path to the filtered no-grid image_features_enriched.csv file.",
    )
    parser.add_argument(
        "--places-csv",
        default="iteration3b/output/no_grid_dataset/places_features.csv",
        help="Path to the Places features CSV generated for the no-grid subset.",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration3b/output/no_grid_dataset",
        help="Directory where enriched, preprocessed, and final CSVs will be written.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).resolve()
    places_csv = Path(args.places_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(input_csv)
    places_by_id = load_places_features(places_csv)
    places_merge_summary = {
        "places_features_path": str(places_csv),
        "places_features_found": places_csv.exists(),
        "places_rows_loaded": len(places_by_id),
        "matched_feature_rows": 0,
        "unmatched_feature_rows": 0,
    }

    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        places_key = (row.get("sensor_id") or row.get("image_id") or "").strip()
        places_row = places_by_id.get(places_key) if places_key else None
        enriched_rows.append(enrich_image_feature_row(row, places_row))
        if places_row is None:
            places_merge_summary["unmatched_feature_rows"] += 1
        else:
            places_merge_summary["matched_feature_rows"] += 1

    feature_sets = {
        "core": [],
        "extended": merge_feature_lists(None, EXTENDED_FEATURE_SET_FALLBACK),
        "phase6_default": merge_feature_lists(None, PHASE6_DEFAULT_FALLBACK),
    }

    enriched_columns = write_csv(
        output_dir / "image_features_enriched.csv",
        enriched_rows,
        preferred_columns=METADATA_COLUMNS + CONTEXT_COLUMNS + TEMPORAL_ENRICHED_COLUMNS + PLACES_ALL_COLUMNS + EXTENDED_FEATURE_SET_FALLBACK,
    )

    preprocessed_rows, eligible_rows, preprocessing_report, scaled_matrix, kept_columns = preprocess_feature_rows(
        enriched_rows,
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
        "input_csv": str(input_csv),
        "places_csv": str(places_csv),
        "output_dir": str(output_dir),
        "input_rows": len(rows),
        "eligible_rows_for_phase5_and_phase6": len(eligible_rows),
        "final_rows": len(reduced_rows),
        "places_merge_summary": places_merge_summary,
        "feature_sets": feature_sets,
        "raw_output_columns": {
            "image_features_enriched_csv": enriched_columns,
            "image_features_preprocessed_csv": preprocessed_columns,
            "image_features_final_csv": final_columns,
        },
        "phase5": preprocessing_report,
        "phase6": reduction_report,
    }
    (output_dir / "iteration2_style_enrichment_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
