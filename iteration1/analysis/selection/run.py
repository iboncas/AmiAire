#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ensure_directory, parse_csv_list, write_csv, write_json
from postprocess_common import (
    cluster_distribution_entropy,
    load_candidate_labels,
    load_benchmark_rows,
    plot_scatter_by_cluster,
    resolve_assignment_path,
    safe_rank_normalize,
)

DEFAULT_ANALYSIS_ROOT = "iteration1/output/analysis"
DEFAULT_OUTPUT_DIR = "iteration1/output/analysis/selection"


def parse_range(raw_value: str) -> tuple[int, int]:
    parts = [part.strip() for part in raw_value.split(",") if part.strip()]
    if len(parts) != 2:
        raise RuntimeError("--preferred-k-range must contain exactly two integers, for example 3,6")
    lower, upper = int(parts[0]), int(parts[1])
    if lower < 2 or upper < lower:
        raise RuntimeError("--preferred-k-range must satisfy 2 <= min <= max")
    return lower, upper


def granularity_score(k_value: int | None, preferred_range: tuple[int, int]) -> float:
    if k_value is None:
        return 0.0
    lower, upper = preferred_range
    if lower <= k_value <= upper:
        return 1.0
    if k_value < lower:
        return max(0.0, 1.0 - 0.35 * (lower - k_value))
    return max(0.0, 1.0 - 0.18 * (k_value - upper))


def selection_plot(output_path: Path, ranked_rows: list[dict[str, Any]]) -> str | None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    filtered_rows = [row for row in ranked_rows if row.get("silhouette_score") is not None and row.get("bootstrap_mean_ari") is not None]
    if not filtered_rows:
        return None

    figure, axis = plt.subplots(figsize=(8, 6))
    method_colors = {
        "kmeans": "#1d3557",
        "ward": "#457b9d",
        "gmm": "#2a9d8f",
        "fuzzy": "#e76f51",
        "hdbscan": "#6d597a",
    }
    for row in filtered_rows:
        color = method_colors.get(row["method"], "#4a4a4a")
        alpha = 0.85 if row["eligible_for_final_selection"] else 0.35
        axis.scatter(
            row["silhouette_score"],
            row["bootstrap_mean_ari"],
            s=50 + 15 * (row.get("num_clusters") or 0),
            color=color,
            alpha=alpha,
        )

    for row in filtered_rows[:10]:
        if not row["eligible_for_final_selection"]:
            continue
        axis.annotate(
            row["candidate_id"],
            (row["silhouette_score"], row["bootstrap_mean_ari"]),
            fontsize=8,
            xytext=(5, 4),
            textcoords="offset points",
        )

    axis.set_xlabel("Silhouette score")
    axis.set_ylabel("Bootstrap mean ARI")
    axis.set_title("Phase 9 selection trade-off plot")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def score_candidates(
    benchmark_rows: list[dict[str, Any]],
    preferred_k_range: tuple[int, int],
    min_repeat_ari: float,
    min_bootstrap_ari: float,
    min_cluster_fraction: float,
    max_noise_fraction: float,
    robustness_only_methods: set[str],
) -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []
    for row in benchmark_rows:
        enriched = dict(row)
        enriched["cluster_entropy"] = cluster_distribution_entropy(row["cluster_size_distribution_values"])
        enriched["granularity_score"] = granularity_score(row.get("num_clusters"), preferred_k_range)

        exclusion_reasons: list[str] = []
        if (row.get("num_clusters") or 0) < 2:
            exclusion_reasons.append("fewer_than_two_clusters")
        if row.get("smallest_cluster_fraction") is None or row["smallest_cluster_fraction"] < min_cluster_fraction:
            exclusion_reasons.append("tiny_cluster")
        if row.get("repeat_mean_ari") is None or row["repeat_mean_ari"] < min_repeat_ari:
            exclusion_reasons.append("repeat_instability")
        if row.get("bootstrap_mean_ari") is None or row["bootstrap_mean_ari"] < min_bootstrap_ari:
            exclusion_reasons.append("bootstrap_instability")
        if row.get("noise_fraction") is not None and row["noise_fraction"] > max_noise_fraction:
            exclusion_reasons.append("excessive_noise")
        if row["method"] in robustness_only_methods:
            exclusion_reasons.append("robustness_only_method")
        if row.get("silhouette_score") is None or row.get("davies_bouldin_score") is None:
            exclusion_reasons.append("missing_internal_metric")

        enriched["exclusion_reasons"] = ",".join(exclusion_reasons)
        enriched["eligible_for_final_selection"] = not exclusion_reasons
        enriched_rows.append(enriched)

    quality_pool = [row for row in enriched_rows if row.get("silhouette_score") is not None]
    if not quality_pool:
        return enriched_rows

    silhouette_scores = [float(row["silhouette_score"]) for row in quality_pool]
    calinski_scores = [float(row["calinski_harabasz_score"] or 0.0) for row in quality_pool]
    davies_scores = [float(row["davies_bouldin_score"]) for row in quality_pool]
    bootstrap_scores = [float(row["bootstrap_mean_ari"] or 0.0) for row in quality_pool]
    repeat_scores = [float(row["repeat_mean_ari"] or 0.0) for row in quality_pool]
    entropy_scores = [float(row["cluster_entropy"] or 0.0) for row in quality_pool]
    min_cluster_scores = [float(row["smallest_cluster_fraction"] or 0.0) for row in quality_pool]

    silhouette_norm = safe_rank_normalize(silhouette_scores, higher_is_better=True)
    calinski_norm = safe_rank_normalize(calinski_scores, higher_is_better=True)
    davies_norm = safe_rank_normalize(davies_scores, higher_is_better=False)
    bootstrap_norm = safe_rank_normalize(bootstrap_scores, higher_is_better=True)
    repeat_norm = safe_rank_normalize(repeat_scores, higher_is_better=True)
    entropy_norm = safe_rank_normalize(entropy_scores, higher_is_better=True)
    min_cluster_norm = safe_rank_normalize(min_cluster_scores, higher_is_better=True)

    for index, row in enumerate(quality_pool):
        row["normalized_silhouette_score"] = silhouette_norm[index]
        row["normalized_calinski_harabasz_score"] = calinski_norm[index]
        row["normalized_davies_bouldin_score"] = davies_norm[index]
        row["normalized_bootstrap_mean_ari"] = bootstrap_norm[index]
        row["normalized_repeat_mean_ari"] = repeat_norm[index]
        row["normalized_cluster_entropy"] = entropy_norm[index]
        row["normalized_smallest_cluster_fraction"] = min_cluster_norm[index]
        row["selection_score"] = (
            0.22 * row["normalized_silhouette_score"]
            + 0.12 * row["normalized_calinski_harabasz_score"]
            + 0.18 * row["normalized_davies_bouldin_score"]
            + 0.18 * row["normalized_bootstrap_mean_ari"]
            + 0.10 * row["normalized_repeat_mean_ari"]
            + 0.10 * row["normalized_cluster_entropy"]
            + 0.05 * row["normalized_smallest_cluster_fraction"]
            + 0.05 * row["granularity_score"]
        )

    for row in enriched_rows:
        row.setdefault("normalized_silhouette_score", None)
        row.setdefault("normalized_calinski_harabasz_score", None)
        row.setdefault("normalized_davies_bouldin_score", None)
        row.setdefault("normalized_bootstrap_mean_ari", None)
        row.setdefault("normalized_repeat_mean_ari", None)
        row.setdefault("normalized_cluster_entropy", None)
        row.setdefault("normalized_smallest_cluster_fraction", None)
        row.setdefault("selection_score", 0.0)

    enriched_rows.sort(
        key=lambda item: (
            bool(item["eligible_for_final_selection"]),
            float(item.get("selection_score") or 0.0),
            float(item.get("silhouette_score") or -1.0),
        ),
        reverse=True,
    )
    return enriched_rows


def trim_selection_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "method": row["method"],
        "feature_space": row["feature_space"],
        "k": row.get("k"),
        "selection_score": row.get("selection_score"),
        "silhouette_score": row.get("silhouette_score"),
        "calinski_harabasz_score": row.get("calinski_harabasz_score"),
        "davies_bouldin_score": row.get("davies_bouldin_score"),
        "repeat_mean_ari": row.get("repeat_mean_ari"),
        "bootstrap_mean_ari": row.get("bootstrap_mean_ari"),
        "smallest_cluster_fraction": row.get("smallest_cluster_fraction"),
        "noise_fraction": row.get("noise_fraction"),
        "cluster_entropy": row.get("cluster_entropy"),
        "eligible_for_final_selection": row["eligible_for_final_selection"],
        "exclusion_reasons": row["exclusion_reasons"],
    }


def compute_candidate_agreements(
    analysis_root: Path,
    reference_candidate_id: str,
    comparison_candidate_ids: list[str],
) -> list[dict[str, Any]]:
    try:
        from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    except ImportError:
        return []

    _reference_rows, reference_lookup = load_candidate_labels(resolve_assignment_path(analysis_root, reference_candidate_id))
    reference_image_ids = sorted(reference_lookup)
    reference_labels = [reference_lookup[image_id] for image_id in reference_image_ids]

    rows = []
    for candidate_id in comparison_candidate_ids:
        if candidate_id == reference_candidate_id:
            continue
        _comparison_rows, comparison_lookup = load_candidate_labels(resolve_assignment_path(analysis_root, candidate_id))
        overlapping_ids = sorted(set(reference_lookup) & set(comparison_lookup))
        if not overlapping_ids:
            continue
        ref = [reference_lookup[image_id] for image_id in overlapping_ids]
        cmp = [comparison_lookup[image_id] for image_id in overlapping_ids]
        rows.append(
            {
                "reference_candidate_id": reference_candidate_id,
                "comparison_candidate_id": candidate_id,
                "overlap_count": len(overlapping_ids),
                "adjusted_rand_index": float(adjusted_rand_score(ref, cmp)),
                "normalized_mutual_information": float(normalized_mutual_info_score(ref, cmp)),
            }
        )
    rows.sort(key=lambda item: item["adjusted_rand_index"], reverse=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Select the final clustering candidate from the Phase 8 benchmark outputs.")
    parser.add_argument("--analysis-root", default=DEFAULT_ANALYSIS_ROOT, help="Directory containing the per-method analysis folders")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory where the selection outputs will be written")
    parser.add_argument(
        "--robustness-only-methods",
        default="hdbscan",
        help="Comma-separated methods to keep as robustness-only checks rather than final-model candidates",
    )
    parser.add_argument("--min-repeat-ari", type=float, default=0.95, help="Minimum repeat-fit ARI required for final selection")
    parser.add_argument("--min-bootstrap-ari", type=float, default=0.95, help="Minimum bootstrap ARI required for final selection")
    parser.add_argument(
        "--min-cluster-fraction",
        type=float,
        default=0.02,
        help="Minimum allowed fraction for the smallest non-noise cluster",
    )
    parser.add_argument("--max-noise-fraction", type=float, default=0.35, help="Maximum allowed noise fraction for a final candidate")
    parser.add_argument(
        "--preferred-k-range",
        default="3,6",
        help="Preferred inclusive cluster-count range used as a small interpretability bonus in the composite score",
    )
    args = parser.parse_args()

    analysis_root = Path(args.analysis_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    ensure_directory(output_dir)

    preferred_k_range = parse_range(args.preferred_k_range)
    robustness_only_methods = set(parse_csv_list(args.robustness_only_methods))
    benchmark_rows = load_benchmark_rows(analysis_root)
    if not benchmark_rows:
        raise RuntimeError(f"No benchmark_results.csv files were found under {analysis_root}")

    ranked_rows = score_candidates(
        benchmark_rows=benchmark_rows,
        preferred_k_range=preferred_k_range,
        min_repeat_ari=args.min_repeat_ari,
        min_bootstrap_ari=args.min_bootstrap_ari,
        min_cluster_fraction=args.min_cluster_fraction,
        max_noise_fraction=args.max_noise_fraction,
        robustness_only_methods=robustness_only_methods,
    )

    all_candidate_rows = [trim_selection_row(row) for row in ranked_rows]
    eligible_rows = [trim_selection_row(row) for row in ranked_rows if row["eligible_for_final_selection"]]
    robustness_rows = [
        trim_selection_row(row)
        for row in ranked_rows
        if row["method"] in robustness_only_methods and not row["eligible_for_final_selection"]
    ]

    recommended_row = next((row for row in ranked_rows if row["eligible_for_final_selection"]), None)
    shortlist_rows = eligible_rows[:10]
    agreement_rows = []
    if recommended_row:
        agreement_rows = compute_candidate_agreements(
            analysis_root=analysis_root,
            reference_candidate_id=recommended_row["candidate_id"],
            comparison_candidate_ids=[row["candidate_id"] for row in shortlist_rows[1:6]],
        )

    write_csv(output_dir / "all_candidates.csv", all_candidate_rows, list(all_candidate_rows[0].keys()))
    write_csv(output_dir / "eligible_candidates.csv", eligible_rows, list(all_candidate_rows[0].keys()))
    write_csv(output_dir / "shortlist.csv", shortlist_rows, list(all_candidate_rows[0].keys()))
    if robustness_rows:
        write_csv(output_dir / "robustness_only_candidates.csv", robustness_rows, list(all_candidate_rows[0].keys()))
    if agreement_rows:
        write_csv(output_dir / "recommended_candidate_agreement.csv", agreement_rows, list(agreement_rows[0].keys()))

    plot_files = {}
    tradeoff_plot = selection_plot(output_dir / "selection_tradeoff_plot.png", ranked_rows)
    if tradeoff_plot:
        plot_files["selection_tradeoff_plot"] = tradeoff_plot

    summary = {
        "analysis_root": str(analysis_root),
        "output_dir": str(output_dir),
        "candidate_count": len(ranked_rows),
        "eligible_candidate_count": len(eligible_rows),
        "robustness_only_methods": sorted(robustness_only_methods),
        "selection_thresholds": {
            "min_repeat_ari": args.min_repeat_ari,
            "min_bootstrap_ari": args.min_bootstrap_ari,
            "min_cluster_fraction": args.min_cluster_fraction,
            "max_noise_fraction": args.max_noise_fraction,
            "preferred_k_range": preferred_k_range,
        },
        "recommended_final_candidate_id": recommended_row["candidate_id"] if recommended_row else None,
        "recommended_final_candidate": trim_selection_row(recommended_row) if recommended_row else None,
        "top_shortlist": shortlist_rows,
        "recommended_candidate_agreement": agreement_rows,
        "best_robustness_only_candidate": robustness_rows[0] if robustness_rows else None,
        "plot_files": plot_files,
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
