#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_SERVICE_SRC = REPO_ROOT / "analysis-service" / "src"
sys.path.insert(0, str(ANALYSIS_SERVICE_SRC))

from taxonomy_model import CATEGORY_WEIGHTS, FeatureProfileScorer


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_rank_lookup(ranked_categories: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {entry["category"]: entry for entry in ranked_categories}


def safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def percentage(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare final cluster-level taxonomy assignments against the direct "
            "formula-based taxonomy scorer for each image row."
        )
    )
    parser.add_argument("--label", required=True, help="Human-readable label for the analyzed iteration")
    parser.add_argument("--feature-csv", required=True, help="Image-level feature CSV used as the taxonomy reference dataset")
    parser.add_argument("--assignments-csv", required=True, help="Final selected clustering assignments CSV")
    parser.add_argument("--taxonomy-suggestions-csv", required=True, help="Cluster-level taxonomy suggestions CSV")
    parser.add_argument("--output-dir", required=True, help="Directory where consistency outputs will be written")
    args = parser.parse_args()

    feature_csv = Path(args.feature_csv).resolve()
    assignments_csv = Path(args.assignments_csv).resolve()
    taxonomy_suggestions_csv = Path(args.taxonomy_suggestions_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    scorer = FeatureProfileScorer(feature_csv)
    feature_rows = read_csv_rows(feature_csv)
    assignment_rows = read_csv_rows(assignments_csv)
    suggestion_rows = read_csv_rows(taxonomy_suggestions_csv)

    feature_by_image_id = {row["image_id"]: row for row in feature_rows if row.get("image_id")}
    suggestion_by_cluster = {int(row["cluster_label"]): row for row in suggestion_rows}
    category_names = list(CATEGORY_WEIGHTS.keys())

    compared_rows: list[dict[str, Any]] = []
    skipped_images: list[dict[str, str]] = []
    cluster_to_direct_categories: dict[int, Counter[str]] = defaultdict(Counter)
    cluster_to_agreement_flags: dict[int, list[int]] = defaultdict(list)
    cluster_to_cluster_pct: dict[int, list[float]] = defaultdict(list)
    cluster_to_top_pct: dict[int, list[float]] = defaultdict(list)
    overall_direct_categories: Counter[str] = Counter()

    for assignment in assignment_rows:
        image_id = assignment.get("image_id", "")
        if not image_id:
            continue
        if assignment.get("noise_flag", "").strip().lower() == "true":
            skipped_images.append({"image_id": image_id, "reason": "noise_row"})
            continue

        feature_row = feature_by_image_id.get(image_id)
        if feature_row is None:
            skipped_images.append({"image_id": image_id, "reason": "missing_feature_row"})
            continue

        cluster_label = int(assignment["cluster_label"])
        cluster_taxonomy = suggestion_by_cluster.get(cluster_label)
        if cluster_taxonomy is None:
            skipped_images.append({"image_id": image_id, "reason": f"missing_cluster_taxonomy:{cluster_label}"})
            continue

        scored = scorer.score_profile(feature_row)
        if scored.get("status") != "ok":
            skipped_images.append({"image_id": image_id, "reason": str(scored.get("message", "scoring_failed"))})
            continue

        ranked = scored["ranked_categories"]
        rank_lookup = build_rank_lookup(ranked)
        top_entry = ranked[0]
        second_entry = ranked[1] if len(ranked) > 1 else {"category": "", "percentage": 0.0}
        cluster_primary_category = cluster_taxonomy["primary_category"]
        cluster_primary_rank = rank_lookup.get(cluster_primary_category, {"percentage": 0.0, "score": 0.0})
        agreement = top_entry["category"] == cluster_primary_category

        overall_direct_categories[top_entry["category"]] += 1
        cluster_to_direct_categories[cluster_label][top_entry["category"]] += 1
        cluster_to_agreement_flags[cluster_label].append(int(agreement))
        cluster_to_cluster_pct[cluster_label].append(float(cluster_primary_rank["percentage"]))
        cluster_to_top_pct[cluster_label].append(float(top_entry["percentage"]))

        compared_rows.append(
            {
                "image_id": image_id,
                "sensor_id": feature_row.get("sensor_id", ""),
                "cluster_label": cluster_label,
                "cluster_primary_category": cluster_primary_category,
                "cluster_confidence": cluster_taxonomy.get("confidence", ""),
                "temp_top_category": top_entry["category"],
                "temp_top_percentage": float(top_entry["percentage"]),
                "temp_second_category": second_entry["category"],
                "temp_second_percentage": float(second_entry["percentage"]),
                "cluster_assigned_percentage_in_temp": float(cluster_primary_rank["percentage"]),
                "cluster_assigned_score_in_temp": float(cluster_primary_rank["score"]),
                "agreement": agreement,
            }
        )

    compared_rows.sort(key=lambda row: (row["cluster_label"], row["image_id"]))

    row_output = output_dir / "row_level_comparison.csv"
    write_csv(
        row_output,
        compared_rows,
        [
            "image_id",
            "sensor_id",
            "cluster_label",
            "cluster_primary_category",
            "cluster_confidence",
            "temp_top_category",
            "temp_top_percentage",
            "temp_second_category",
            "temp_second_percentage",
            "cluster_assigned_percentage_in_temp",
            "cluster_assigned_score_in_temp",
            "agreement",
        ],
    )

    cluster_summary_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    for cluster_label in sorted(cluster_to_agreement_flags):
        cluster_row_count = len(cluster_to_agreement_flags[cluster_label])
        taxonomy_row = suggestion_by_cluster[cluster_label]
        top_direct_category, top_direct_count = cluster_to_direct_categories[cluster_label].most_common(1)[0]
        cluster_summary_rows.append(
            {
                "cluster_label": cluster_label,
                "cluster_primary_category": taxonomy_row["primary_category"],
                "cluster_confidence": taxonomy_row.get("confidence", ""),
                "row_count": cluster_row_count,
                "agreement_count": sum(cluster_to_agreement_flags[cluster_label]),
                "agreement_rate": sum(cluster_to_agreement_flags[cluster_label]) / cluster_row_count,
                "dominant_temp_category": top_direct_category,
                "dominant_temp_category_count": top_direct_count,
                "dominant_temp_category_fraction": top_direct_count / cluster_row_count,
                "mean_cluster_assigned_percentage_in_temp": safe_mean(cluster_to_cluster_pct[cluster_label]),
                "mean_temp_top_percentage": safe_mean(cluster_to_top_pct[cluster_label]),
            }
        )
        for category in category_names:
            count = cluster_to_direct_categories[cluster_label][category]
            confusion_rows.append(
                {
                    "cluster_label": cluster_label,
                    "cluster_primary_category": taxonomy_row["primary_category"],
                    "temp_top_category": category,
                    "count": count,
                    "fraction_within_cluster": count / cluster_row_count if cluster_row_count else 0.0,
                }
            )

    cluster_summary_output = output_dir / "cluster_summary.csv"
    write_csv(
        cluster_summary_output,
        cluster_summary_rows,
        [
            "cluster_label",
            "cluster_primary_category",
            "cluster_confidence",
            "row_count",
            "agreement_count",
            "agreement_rate",
            "dominant_temp_category",
            "dominant_temp_category_count",
            "dominant_temp_category_fraction",
            "mean_cluster_assigned_percentage_in_temp",
            "mean_temp_top_percentage",
        ],
    )

    confusion_output = output_dir / "cluster_vs_temp_confusion.csv"
    write_csv(
        confusion_output,
        confusion_rows,
        [
            "cluster_label",
            "cluster_primary_category",
            "temp_top_category",
            "count",
            "fraction_within_cluster",
        ],
    )

    agreement_values = [int(row["agreement"]) for row in compared_rows]
    cluster_assigned_percentages = [float(row["cluster_assigned_percentage_in_temp"]) for row in compared_rows]
    top_percentages = [float(row["temp_top_percentage"]) for row in compared_rows]

    summary = {
        "label": args.label,
        "feature_csv": str(feature_csv),
        "assignments_csv": str(assignments_csv),
        "taxonomy_suggestions_csv": str(taxonomy_suggestions_csv),
        "output_dir": str(output_dir),
        "row_count_compared": len(compared_rows),
        "row_count_skipped": len(skipped_images),
        "overall_agreement_rate": safe_mean(agreement_values),
        "mean_cluster_assigned_percentage_in_temp": safe_mean(cluster_assigned_percentages),
        "mean_temp_top_percentage": safe_mean(top_percentages),
        "overall_temp_top_category_distribution": dict(overall_direct_categories),
        "category_names": category_names,
        "notes": [
            "This is a consistency check, not ground truth validation.",
            "The TEMP scorer and the cluster taxonomy use the same hand-crafted category definitions, so they are not statistically independent.",
            "Agreement suggests internal coherence between cluster-level interpretation and row-level direct formula scoring.",
            "Disagreement suggests within-cluster mixture, ambiguous rows, or sensitivity to aggregation at the cluster-profile level.",
        ],
        "artifacts": {
            "row_level_comparison_csv": str(row_output),
            "cluster_summary_csv": str(cluster_summary_output),
            "cluster_vs_temp_confusion_csv": str(confusion_output),
        },
    }
    if skipped_images:
        summary["skipped_examples"] = skipped_images[:20]

    summary_output = output_dir / "summary.json"
    write_json(summary_output, summary)

    lines = [
        "# TEMP Taxonomy Consistency Check",
        "",
        f"Iteration: `{args.label}`",
        "",
        "This compares each image row's direct TEMP taxonomy result against the final cluster-level taxonomy label.",
        "",
        "Important note:",
        "This is **not** ground truth. Both sides come from the same heuristic taxonomy family, so this should be interpreted as an internal consistency audit.",
        "",
        "## Overall",
        "",
        f"- Rows compared: `{len(compared_rows)}`",
        f"- Rows skipped: `{len(skipped_images)}`",
        f"- Direct TEMP top-category agreement with cluster label: `{percentage(safe_mean(agreement_values))}`",
        f"- Mean TEMP percentage assigned to the cluster's chosen category: `{safe_mean(cluster_assigned_percentages):.2f}`",
        f"- Mean TEMP percentage of each row's own top category: `{safe_mean(top_percentages):.2f}`",
        "",
        "## Cluster Summary",
        "",
        "| Cluster | Cluster taxonomy | Agreement | Dominant TEMP category | Mean TEMP support for cluster label |",
        "| --- | --- | ---: | --- | ---: |",
    ]

    for row in cluster_summary_rows:
        lines.append(
            f"| `{row['cluster_label']}` | `{row['cluster_primary_category']}` | `{percentage(float(row['agreement_rate']))}` | "
            f"`{row['dominant_temp_category']}` | `{float(row['mean_cluster_assigned_percentage_in_temp']):.2f}` |"
        )

    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- `row_level_comparison.csv`",
            f"- `cluster_summary.csv`",
            f"- `cluster_vs_temp_confusion.csv`",
            f"- `summary.json`",
        ]
    )
    write_text(output_dir / "RESULTS.md", "\n".join(lines) + "\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
