#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ensure_directory, write_csv, write_json
from postprocess_common import load_csv_rows, plot_heatmap

DEFAULT_EXPLAINABILITY_DIR = "iteration1/output/analysis/explainability"
DEFAULT_OUTPUT_DIR = "iteration1/output/analysis/taxonomy"

CATEGORY_WEIGHTS: dict[str, dict[str, float]] = {
    "combustion_related": {
        "num_particles": 1.15,
        "area_median": -1.05,
        "feret_p90": -0.85,
        "circularity_median": 0.95,
        "aspect_ratio_median": -0.80,
        "eccentricity_p90": -0.70,
        "mean_intensity_median": 0.40,
    },
    "mechanical_non_combustion_particulate": {
        "area_median": 1.05,
        "feret_p90": 0.95,
        "solidity_median": 0.85,
        "num_particles": -0.30,
        "solidity_iqr": 0.80,
        "aspect_ratio_iqr": 0.65,
        "circularity_median": -0.70,
        "mean_intensity_iqr": 0.45,
        "feret_iqr": 0.55,
    },
    "biological": {
        "area_iqr": 0.85,
        "mean_intensity_iqr": 0.90,
        "circularity_iqr": 0.70,
        "orientation_entropy": 0.55,
        "aspect_ratio_iqr": 0.45,
        "circular_variance": 0.40,
    },
    "fibrous_synthetic_materials": {
        "aspect_ratio_median": 1.20,
        "aspect_ratio_p90": 1.15,
        "eccentricity_p90": 1.00,
        "feret_p90": 0.90,
        "circularity_median": -1.00,
        "solidity_median": -0.45,
        "eccentricity_iqr": 0.60,
    },
    "industrial": {
        "solidity_iqr": 0.85,
        "eccentricity_iqr": 0.80,
        "feret_iqr": 0.80,
        "mean_intensity_iqr": 0.70,
        "orientation_entropy": 0.55,
        "aspect_ratio_iqr": 0.40,
    },
    "mixed_unknown": {
        "orientation_entropy": 0.95,
        "circular_variance": 0.90,
        "area_iqr": 0.80,
        "circularity_iqr": 0.80,
        "mean_intensity_iqr": 0.70,
        "solidity_iqr": 0.55,
    },
}


def load_standardized_profiles(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    rows = load_csv_rows(path)
    if not rows:
        raise RuntimeError(f"Cluster profile CSV is empty: {path}")
    feature_columns = [
        column
        for column in rows[0].keys()
        if column not in {"cluster_label", "count", "fraction"}
    ]
    return rows, feature_columns


def contribution_summary(
    category: str,
    row: dict[str, str],
) -> tuple[float, list[tuple[str, float, float]]]:
    weights = CATEGORY_WEIGHTS[category]
    contributions = []
    score = 0.0
    for feature_name, weight in weights.items():
        raw_value = row.get(feature_name)
        if raw_value in (None, ""):
            continue
        value = float(raw_value)
        contribution = value * weight
        score += contribution
        contributions.append((feature_name, contribution, value))
    contributions.sort(key=lambda item: abs(item[1]), reverse=True)
    return score, contributions


def confidence_label(top_score: float, score_gap: float) -> str:
    if top_score < 0.5 or score_gap < 0.25:
        return "low"
    if top_score >= 1.5 and score_gap >= 0.8:
        return "high"
    return "moderate"


def load_cluster_descriptions(path: Path) -> dict[int, dict[str, str]]:
    if not path.exists():
        return {}
    rows = load_csv_rows(path)
    return {int(row["cluster_label"]): row for row in rows}


def describe_evidence(contributions: list[tuple[str, float, float]]) -> str:
    phrases = []
    for feature_name, contribution, standardized_value in contributions[:4]:
        direction = "higher" if standardized_value >= 0 else "lower"
        phrases.append(f"{direction} {feature_name} (z={standardized_value:+.2f}, score={contribution:+.2f})")
    return "; ".join(phrases)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a cautious source-taxonomy interpretation layer for the final clusters.")
    parser.add_argument(
        "--explainability-dir",
        default=DEFAULT_EXPLAINABILITY_DIR,
        help="Directory produced by iteration1/analysis/explainability/run.py",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory where taxonomy outputs will be written")
    parser.add_argument(
        "--min-primary-score",
        type=float,
        default=0.5,
        help="Minimum score required before a non-mixed category is accepted as the primary suggestion",
    )
    parser.add_argument(
        "--ambiguity-gap",
        type=float,
        default=0.25,
        help="Minimum score gap between the top two categories before the primary label is treated as non-ambiguous",
    )
    args = parser.parse_args()

    explainability_dir = Path(args.explainability_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    ensure_directory(output_dir)

    profile_rows, feature_columns = load_standardized_profiles(explainability_dir / "cluster_profile_standardized.csv")
    cluster_descriptions = load_cluster_descriptions(explainability_dir / "cluster_descriptions.csv")

    long_rows: list[dict[str, Any]] = []
    suggestion_rows: list[dict[str, Any]] = []
    heatmap_matrix = []
    category_names = list(CATEGORY_WEIGHTS.keys())

    for row in profile_rows:
        category_scores = []
        category_contributions: dict[str, list[tuple[str, float, float]]] = {}
        for category in category_names:
            score, contributions = contribution_summary(category, row)
            category_scores.append((category, score))
            category_contributions[category] = contributions
            long_rows.append(
                {
                    "cluster_label": int(row["cluster_label"]),
                    "category": category,
                    "score": score,
                }
            )

        category_scores.sort(key=lambda item: item[1], reverse=True)
        heatmap_matrix.append([score for _category, score in category_scores])
        primary_category, primary_score = category_scores[0]
        secondary_category, secondary_score = category_scores[1]
        score_gap = primary_score - secondary_score

        if primary_score < args.min_primary_score or score_gap < args.ambiguity_gap:
            final_primary = "mixed_unknown"
        else:
            final_primary = primary_category

        description_row = cluster_descriptions.get(int(row["cluster_label"]), {})
        suggestion_rows.append(
            {
                "cluster_label": int(row["cluster_label"]),
                "primary_category": final_primary,
                "primary_score": primary_score,
                "secondary_category": secondary_category,
                "secondary_score": secondary_score,
                "score_gap": score_gap,
                "confidence": confidence_label(primary_score, score_gap),
                "morphology_summary": description_row.get("morphology_summary", ""),
                "evidence_summary": describe_evidence(category_contributions[final_primary]),
            }
        )

    long_rows.sort(key=lambda item: (item["cluster_label"], item["score"]), reverse=True)
    suggestion_rows.sort(key=lambda item: item["cluster_label"])

    write_csv(output_dir / "taxonomy_scores.csv", long_rows, list(long_rows[0].keys()))
    write_csv(output_dir / "taxonomy_suggestions.csv", suggestion_rows, list(suggestion_rows[0].keys()))

    heatmap_rows = sorted({row["cluster_label"] for row in long_rows})
    heatmap_values = np.array(
        [
            [next(item["score"] for item in long_rows if item["cluster_label"] == cluster and item["category"] == category) for category in category_names]
            for cluster in heatmap_rows
        ],
        dtype=np.float64,
    )
    plot_files = {}
    score_heatmap = plot_heatmap(
        output_path=output_dir / "taxonomy_score_heatmap.png",
        matrix=heatmap_values,
        row_labels=[f"cluster {cluster}" for cluster in heatmap_rows],
        column_labels=category_names,
        title="Cluster-to-taxonomy score heatmap",
        cmap="viridis",
    )
    if score_heatmap:
        plot_files["taxonomy_score_heatmap"] = score_heatmap

    summary = {
        "explainability_dir": str(explainability_dir),
        "output_dir": str(output_dir),
        "categories": category_names,
        "cluster_count": len(profile_rows),
        "notes": [
            "These labels are cautious morphology-based source-category suggestions, not chemical identification claims.",
            "The scoring rules are heuristic and intended to support thesis discussion, not replace laboratory validation.",
        ],
        "plot_files": plot_files,
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
