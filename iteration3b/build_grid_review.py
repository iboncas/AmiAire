#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


REQUIRED_COLUMNS = [
    "image_id",
    "roi_grid_label",
    "roi_grid_score",
    "roi_grid_confidence",
    "roi_grid_needs_review",
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"Missing required columns in {path}: {', '.join(missing)}. "
                "Rebuild the dataset with the ROI grid detector first."
            )
        return rows


def to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def select_sample(rows: list[dict[str, str]], per_bucket: int) -> list[dict[str, str]]:
    predicted_grid = [row for row in rows if row["roi_grid_label"] == "grid"]
    predicted_no_grid = [row for row in rows if row["roi_grid_label"] == "no_grid"]
    uncertain = [row for row in rows if row["roi_grid_label"] == "uncertain" or to_bool(row["roi_grid_needs_review"])]

    predicted_grid.sort(key=lambda row: (-to_float(row["roi_grid_score"]), -to_float(row["roi_grid_confidence"])))
    predicted_no_grid.sort(key=lambda row: (to_float(row["roi_grid_score"]), -to_float(row["roi_grid_confidence"])))
    uncertain.sort(key=lambda row: (abs(to_float(row["roi_grid_score"]) - 0.42), -to_float(row["roi_grid_confidence"])))

    picked = []
    seen_ids = set()
    for bucket in (
        predicted_no_grid[:per_bucket],
        predicted_grid[:per_bucket],
        uncertain[:per_bucket],
    ):
        for row in bucket:
            image_id = row.get("image_id")
            if image_id in seen_ids:
                continue
            review_row = dict(row)
            review_row["manual_grid_label"] = ""
            review_row["manual_review_notes"] = ""
            picked.append(review_row)
            seen_ids.add(image_id)
    return picked


def build_simple_review_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    simple_rows = []
    for row in rows:
        simple_rows.append(
            {
                "image_id": row.get("image_id", ""),
                "roi_grid_label": row.get("roi_grid_label", ""),
                "manual_grid_label": "",
            }
        )
    return simple_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build manual-review CSVs for ROI grid filtering.")
    parser.add_argument(
        "--input-csv",
        default="iteration3b/output/dataset/image_features_enriched.csv",
        help="Dataset CSV that contains ROI grid prediction columns.",
    )
    parser.add_argument(
        "--output-dir",
        default="iteration3b/output/grid_review",
        help="Directory where review CSVs will be written.",
    )
    parser.add_argument(
        "--per-bucket",
        type=int,
        default=20,
        help="Number of images to sample from each bucket: no_grid, grid, and uncertain.",
    )
    parser.add_argument(
        "--mode",
        choices=["sample", "all"],
        default="sample",
        help="Write only one minimal CSV, either for the sampled review set or for all rows.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    rows = load_rows(input_csv)
    rows.sort(key=lambda row: (to_float(row["roi_grid_score"]), row.get("image_id", "")))

    review_all = []
    for row in rows:
        enriched = dict(row)
        enriched["manual_grid_label"] = ""
        enriched["manual_review_notes"] = ""
        review_all.append(enriched)

    sample_rows = select_sample(rows, max(1, args.per_bucket))
    selected_rows = sample_rows if args.mode == "sample" else review_all
    simple_rows = build_simple_review_rows(selected_rows)
    simple_fieldnames = ["image_id", "roi_grid_label", "manual_grid_label"]
    output_name = "grid_review_simple.csv"

    write_rows(output_dir / output_name, simple_rows, simple_fieldnames)
    print(f"Wrote {len(simple_rows)} rows to {output_dir / output_name}")


if __name__ == "__main__":
    main()
