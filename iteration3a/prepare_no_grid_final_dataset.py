#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from iteration2.build_dataset import (  # type: ignore
    EXTENDED_FEATURE_SET_FALLBACK,
    ID_COLUMNS,
    PHASE6_DEFAULT_FALLBACK,
    preprocess_feature_rows,
    reduce_feature_rows,
    write_csv,
)


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare image_features_preprocessed.csv and image_features_final.csv from the no-grid enriched dataset."
    )
    parser.add_argument(
        "--input-csv",
        default="iteration3a/output/no_grid_dataset/image_features_enriched.csv",
        help="Path to the no-grid image_features_enriched.csv file.",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration3a/output/no_grid_dataset",
        help="Directory where preprocessed and final CSVs will be written.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    rows = load_rows(input_csv)
    feature_sets = {
        "core": [],
        "extended": EXTENDED_FEATURE_SET_FALLBACK,
        "phase6_default": PHASE6_DEFAULT_FALLBACK,
    }

    preprocessed_rows, eligible_rows, preprocessing_report, scaled_matrix, kept_columns = preprocess_feature_rows(
        rows,
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
        "output_dir": str(output_dir),
        "input_rows": len(rows),
        "eligible_rows_for_phase5_and_phase6": len(eligible_rows),
        "preprocessed_rows": len(preprocessed_rows),
        "final_rows": len(reduced_rows),
        "preprocessed_columns": preprocessed_columns,
        "final_columns": final_columns,
        "phase5": preprocessing_report,
        "phase6": reduction_report,
    }
    write_csv(
        output_dir / "dataset_preparation_summary.csv",
        [
            {
                "input_rows": len(rows),
                "eligible_rows_for_phase5_and_phase6": len(eligible_rows),
                "preprocessed_rows": len(preprocessed_rows),
                "final_rows": len(reduced_rows),
                "selected_feature_count": len(reduction_report.get("selected_columns", [])),
            }
        ],
        preferred_columns=[
            "input_rows",
            "eligible_rows_for_phase5_and_phase6",
            "preprocessed_rows",
            "final_rows",
            "selected_feature_count",
        ],
    )
    (output_dir / "dataset_preparation_report.json").write_text(__import__("json").dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(__import__("json").dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
