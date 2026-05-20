#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark_common import (
    build_assignments_rows,
    build_candidate_id,
    compute_bootstrap_stability,
    compute_internal_metrics,
    compute_repeat_stability,
    normalize_labels,
    plot_metric_by_k,
    require_sklearn_metrics,
    summarize_benchmark_results,
    trim_ranked_results,
    write_assignments_csv,
)
from common import (
    BENCHMARK_COLUMNS,
    DEFAULT_PHASE6_INPUT_CSV,
    DEFAULT_PCA_SCORES_INPUT_CSV,
    ensure_directory,
    parse_csv_list,
    parse_k_values,
    write_csv,
    write_json,
)
from input_spaces import (
    load_requested_feature_spaces,
    validate_feature_spaces,
    validate_k_values,
    validate_row_count_for_clustering,
)

DEFAULT_OUTPUT_DIR = "iteration1/output/analysis/ward"


def require_agglomerative() -> Any:
    try:
        from sklearn.cluster import AgglomerativeClustering
    except ImportError as error:
        raise SystemExit(
            "scikit-learn is required for phase 8 Ward clustering. "
            "Install it with `pip install -r requirements.txt`."
        ) from error
    return AgglomerativeClustering


def fit_predict_ward(
    features: np.ndarray,
    candidate: dict[str, Any],
    random_seed: int,
    shuffle_seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray | None, dict[str, Any]]:
    del random_seed
    agglomerative_cls = require_agglomerative()
    n_rows = features.shape[0]
    order = np.arange(n_rows) if shuffle_seed is None else np.random.default_rng(shuffle_seed).permutation(n_rows)
    shuffled_features = features[order, :]

    model = agglomerative_cls(n_clusters=candidate["k"], linkage="ward")
    labels_shuffled = model.fit_predict(shuffled_features)

    restored_labels = np.full(n_rows, -1, dtype=int)
    restored_labels[order] = normalize_labels(labels_shuffled)
    return restored_labels, None, {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Ward-linkage benchmark.")
    parser.add_argument("--selected-input-csv", default=DEFAULT_PHASE6_INPUT_CSV, help="Path to image_features_final.csv")
    parser.add_argument(
        "--pca-input-csv",
        default=DEFAULT_PCA_SCORES_INPUT_CSV,
        help="Path to the Phase 7 pca_scores_retained.csv file",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory where benchmark outputs will be written")
    parser.add_argument("--sample-size", type=int, default=0, help="Optional random sample size; 0 keeps all aligned rows")
    parser.add_argument("--random-seed", type=int, default=7, help="Base random seed")
    parser.add_argument(
        "--feature-spaces",
        default="selected_features,pca_scores",
        help="Comma-separated feature spaces to benchmark: selected_features, pca_scores",
    )
    parser.add_argument("--k-values", default="2,3,4,5,6,7,8", help="Comma-separated cluster counts")
    parser.add_argument("--stability-repeats", type=int, default=10, help="Number of repeated full-data fits")
    parser.add_argument("--bootstrap-repeats", type=int, default=10, help="Number of bootstrap refits")
    parser.add_argument("--bootstrap-fraction", type=float, default=0.8, help="Fraction used in each bootstrap run")
    args = parser.parse_args()

    feature_spaces = parse_csv_list(args.feature_spaces)
    validate_feature_spaces(feature_spaces)
    k_values = parse_k_values(args.k_values)

    output_dir = Path(args.output_dir).resolve()
    ensure_directory(output_dir)
    assignments_dir = output_dir / "assignments"
    ensure_directory(assignments_dir)

    loaded = load_requested_feature_spaces(
        selected_input_csv=Path(args.selected_input_csv).resolve(),
        pca_input_csv=Path(args.pca_input_csv).resolve() if "pca_scores" in feature_spaces else None,
        feature_spaces=feature_spaces,
        sample_size=args.sample_size,
        random_seed=args.random_seed,
    )
    metadata_rows = loaded["metadata_rows"]
    feature_space_map = loaded["feature_space_map"]
    validate_row_count_for_clustering(len(metadata_rows))
    validate_k_values(len(metadata_rows), k_values)

    metrics_lib = require_sklearn_metrics()
    benchmark_results = []

    for feature_space in feature_spaces:
        features = feature_space_map[feature_space]
        for k_value in k_values:
            candidate = {
                "feature_space": feature_space,
                "method": "ward",
                "k": k_value,
                "covariance_type": "",
            }
            candidate_id = build_candidate_id(candidate)
            labels, confidence, extras = fit_predict_ward(features, candidate, random_seed=args.random_seed)
            metrics = compute_internal_metrics(features, labels, metrics_lib)
            repeat_mean_ari, repeat_std_ari = compute_repeat_stability(
                features,
                candidate,
                repeats=args.stability_repeats,
                base_seed=args.random_seed,
                fit_predict=fit_predict_ward,
                adjusted_rand_score=metrics_lib["adjusted_rand_score"],
            )
            bootstrap_mean_ari, bootstrap_std_ari = compute_bootstrap_stability(
                features,
                labels,
                candidate,
                repeats=args.bootstrap_repeats,
                sample_fraction=args.bootstrap_fraction,
                base_seed=args.random_seed,
                fit_predict=fit_predict_ward,
                adjusted_rand_score=metrics_lib["adjusted_rand_score"],
            )

            assignment_rows = build_assignments_rows(
                metadata_rows,
                labels,
                confidence,
                candidate_id=candidate_id,
                feature_space=feature_space,
                method="ward",
                method_variant="ward",
            )
            write_assignments_csv(assignments_dir / f"{candidate_id}.csv", assignment_rows)

            benchmark_results.append(
                {
                    "candidate_id": candidate_id,
                    "feature_space": feature_space,
                    "method": "ward",
                    "method_variant": "ward",
                    "k": k_value,
                    "covariance_type": "",
                    "min_cluster_size": None,
                    "min_samples": None,
                    "random_seed": args.random_seed,
                    "num_clusters": metrics["num_clusters"],
                    "noise_points": metrics["noise_points"],
                    "noise_fraction": metrics["noise_fraction"],
                    "smallest_cluster_fraction": metrics["smallest_cluster_fraction"],
                    "largest_cluster_fraction": metrics["largest_cluster_fraction"],
                    "tiny_cluster_flag": metrics["tiny_cluster_flag"],
                    "silhouette_score": metrics["silhouette_score"],
                    "calinski_harabasz_score": metrics["calinski_harabasz_score"],
                    "davies_bouldin_score": metrics["davies_bouldin_score"],
                    "bic": extras.get("bic"),
                    "aic": extras.get("aic"),
                    "fuzzy_partition_coefficient": extras.get("fuzzy_partition_coefficient"),
                    "partition_entropy": extras.get("partition_entropy"),
                    "repeat_mean_ari": repeat_mean_ari,
                    "repeat_std_ari": repeat_std_ari,
                    "bootstrap_mean_ari": bootstrap_mean_ari,
                    "bootstrap_std_ari": bootstrap_std_ari,
                    "cluster_size_distribution": metrics["cluster_size_distribution"],
                }
            )

    write_csv(output_dir / "benchmark_results.csv", benchmark_results, BENCHMARK_COLUMNS)
    silhouette_plot = plot_metric_by_k(
        output_dir / "silhouette_by_k.png",
        benchmark_results,
        metric_name="silhouette_score",
        title="Ward silhouette benchmark",
        label_builder=lambda result: result["feature_space"],
    )
    ranked_results = summarize_benchmark_results(benchmark_results)
    trimmed_rankings = {key: trim_ranked_results(value) for key, value in ranked_results.items()}

    summary = {
        "selected_input_csv": loaded["loaded_paths"].get("selected_features"),
        "pca_input_csv": loaded["loaded_paths"].get("pca_scores"),
        "output_dir": str(output_dir),
        "rows_by_loaded_space": loaded["row_counts_by_space"],
        "rows_used": len(metadata_rows),
        "sample_size_argument": args.sample_size,
        "sampled_indices": loaded["sampled_indices"],
        "feature_spaces": feature_spaces,
        "k_values": k_values,
        "stability_repeats": args.stability_repeats,
        "bootstrap_repeats": args.bootstrap_repeats,
        "bootstrap_fraction": args.bootstrap_fraction,
        "benchmark_results_csv": str(output_dir / "benchmark_results.csv"),
        "assignments_dir": str(assignments_dir),
        "plot_files": {"silhouette_by_k": silhouette_plot} if silhouette_plot else {},
        "rankings": trimmed_rankings,
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
